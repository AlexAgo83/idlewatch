"""Read-only decoder for Melvor Idle 2 saves (a Brotli stream holding a .NET BinaryWriter layout).

A save starts with a header (character, mode, time, current activity, totals), then a table of
entities, each a table of components. Skills are entities with an Experience component: float64 xp, then
an int32 level in the demo (12 bytes); the release (save version 31) keeps the xp only (8 bytes) and the level
comes from the game's xp curve. The bank is MelvorBase:Bank with Inventory and Wallet components. Bank items
are kept by short name with their quantity; placeholders (stacks with quantity 0) are left out.
"""
from __future__ import annotations

import datetime
import math
import struct
import uuid

import brotli


class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data, self.pos = data, pos

    def take(self, n: int) -> bytes:
        value = self.data[self.pos:self.pos + n]
        if len(value) != n:
            raise ValueError(f"Truncated save at byte {self.pos}")
        self.pos += n
        return value

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.take(8))[0]

    def f64(self) -> float:
        return struct.unpack("<d", self.take(8))[0]

    def flag(self) -> bool:
        return self.take(1) != b"\0"

    def count(self) -> int:
        n = self.i32()
        if n < 0 or n > len(self.data):
            raise ValueError(f"Invalid count {n} at byte {self.pos - 4}")
        return n

    def text(self) -> str:
        # .NET BinaryWriter: 7-bit encoded byte length, then UTF-8.
        n = shift = 0
        while True:
            byte = self.take(1)[0]
            n |= (byte & 0x7F) << shift
            if byte < 0x80:
                return self.take(n).decode("utf-8")
            shift += 7
            if shift > 28:
                raise ValueError("Invalid string length")


def saved_at(binary: int) -> str:
    # DateTime.ToBinary: Utc and Local kinds both store UTC ticks below the two kind bits.
    ticks = binary & 0x3FFFFFFFFFFFFFFF
    when = datetime.datetime(1, 1, 1, tzinfo=datetime.UTC) + datetime.timedelta(microseconds=ticks // 10)
    return when.isoformat(timespec="seconds").replace("+00:00", "Z")


def _table(reader: Reader) -> dict[str, tuple[int, int]]:
    """Name -> (offset, size) for a length-prefixed table of named blobs, skipped over."""
    found = {}
    for _ in range(reader.count()):
        name, size = reader.text(), reader.i32()
        if size < 0 or reader.pos + size > len(reader.data):
            raise ValueError(f"Invalid size for {name}")
        found[name] = (reader.pos, size)
        reader.pos += size
    return found


def level_for(xp: float) -> int:
    """The level an xp total reaches on Melvor's curve (it matches every demo save that still stored both)."""
    level, total = 1, 0.0
    while level < 200:
        total += math.floor(level + 300 * 2 ** (level / 7))
        if math.floor(total / 4) > xp:
            return level
        level += 1
    return level


def _short(name: str) -> str:
    return name.split(":", 1)[-1]


def _astrology(action: bytes) -> dict:
    """Recognize a complete constellation list after a small opaque Action header."""
    empty = {"constellations": [], "active": None}

    def identifier(reader: Reader, optional: bool = False) -> str | None:
        name = reader.text()
        if optional and not name:
            return None
        namespace, separator, short = name.partition(":")
        if not separator or not namespace or not short or any(c.isspace() or ord(c) < 32 for c in name):
            raise ValueError("Invalid Astrology id")
        return short

    # The Action header is not documented. Accept at most 16 opaque bytes, and only
    # recognize the layout when every record and the final active id consume the blob.
    # Keep this reader bounded to Action so an unknown layout cannot consume another component.
    for start in range(min(17, len(action))):
        r = Reader(action, start)
        try:
            constellations = []
            ids = set()
            for _ in range(r.count()):
                name = identifier(r)
                value, xp = r.i32(), r.f64()
                if name in ids or not math.isfinite(xp) or xp < 0:
                    raise ValueError("Invalid Astrology constellation")
                ids.add(name)
                minor = [identifier(r) for _ in range(r.count())]
                major = [identifier(r) for _ in range(r.count())]
                constellations.append({"id": name, "value": value, "xp": xp,
                                       "minor": minor, "major": major})
            if (active := _active(r, identifier)) is not False and (active is None or active in ids):
                return {"constellations": constellations, "active": active}
        except ValueError:
            continue
    return empty


def _active(r: Reader, identifier) -> str | bool | None:
    """The active constellation that ends the Action blob, or False when the tail is not recognized.

    Early release saves end with the id itself; later ones (2026-11) write a presence flag, the id when set, then
    two zero bytes. Both must consume the blob exactly, so another layout is never misread.
    """
    start = r.pos
    try:
        active = identifier(r, optional=True)
        if r.pos == len(r.data):
            return active
    except ValueError:
        pass
    r.pos = start
    try:
        flag = r.take(1)[0]
        if flag > 1:
            return False
        active = identifier(r) if flag else None
        tail = r.data[r.pos:]
        return active if len(tail) <= 4 and not tail.strip(b"\0") else False
    except ValueError:
        return False


def _records(blob: bytes) -> tuple[list[tuple[str, bytes]], bytes]:
    """A count, then (id, int32 size, payload) records: the shape of most named-state components; and what
    follows them (Equipment keeps its loadouts there, Slayer Tasks its active master)."""
    r = Reader(blob)
    out = []
    for _ in range(r.count()):
        name, size = r.text(), r.i32()
        if size < 0:
            raise ValueError("Invalid record size")
        out.append((name, r.take(size)))
    return out, blob[r.pos:]


def _ids(blob: bytes) -> list[str]:
    """Every length-prefixed MelvorBase id inside a payload, in order (short names)."""
    found, i = [], 0
    while i < len(blob):
        n = blob[i]
        word = blob[i + 1:i + 1 + n]
        if 12 <= n < 0x80 and word.startswith(b"MelvorBase:") and word.isascii() and all(32 < c < 127 for c in word):
            found.append(_short(word.decode()))
            i += 1 + n
        else:
            i += 1
    return found


def _equipment(blob: bytes) -> dict:
    """Slot -> {item, quantity}; an empty slot (quantity -1, no item) is left out."""
    out = {}
    for slot, payload in _records(blob)[0]:
        r = Reader(payload)
        quantity, _, has = r.i32(), r.flag(), r.flag()
        if has:
            out[_short(slot)] = {"item": _short(r.text()), "quantity": quantity}
    return out


def _mastery(blob: bytes) -> dict:
    """The skill's mastery guild tasks: done ids, in-progress ids with their progress, and untouched counts."""
    r = Reader(blob)
    if r.flag():
        r.text()  # last opened category, a UI choice
    done, progress, untouched = [], {}, 0
    for _ in range(r.count()):
        name, size = _short(r.text()), r.i32()
        payload = Reader(r.take(size))
        if size == 2:
            untouched += 1
            continue
        payload.flag()
        payload.text()  # goal key within the task
        payload.i32()
        value, complete = payload.f64(), payload.flag()
        if complete:
            done.append(name)
        elif value > 0:
            progress[name] = round(value, 1)
    return {"done": done, "progress": progress, "untouched": untouched}


def _slayer(blob: bytes) -> dict:
    """Master -> current task monster (when one is set), the two counters after it (meaning unverified) and
    the monsters it is told to skip; the master whose task is active is flagged."""
    out = {}
    records, tail = _records(blob)
    tail_reader = Reader(tail)
    active = _short(tail_reader.text()) if tail and tail_reader.flag() else None
    for master, payload in records:
        r = Reader(payload)
        if not r.flag():
            continue
        monster, first, second = _short(r.text()), r.i32(), r.i32()
        out[_short(master)] = {"monster": monster, "counters": [first, second], "active": _short(master) == active,
                               "blocked": [i for i in _ids(payload[r.pos:]) if i != monster]}
    return out


def _farming(blob: bytes) -> dict:
    """Plot -> its crop (the first id in the plot's record); an empty plot is left out."""
    r = Reader(blob)
    if r.flag():
        r.text()  # grain mill farm
        r.take(8)
    out = {}
    for _ in range(r.count()):
        plot, size = _short(r.text()), r.i32()
        ids = _ids(r.take(size))
        if ids:
            out[plot] = {"crop": ids[0], "fertilised": "Fertiliser" in ids[1:]}
    return out


def _ranching(blob: bytes) -> list[dict]:
    """Ranching land in use: its enclosure, the enclosure's condition and each animal (species, variant, three
    gauges in save order, presumably hunger, comfort and satisfaction, and its treat slots). Empty land is left out."""
    start = blob.find(b"MelvorBase:Land")
    if start < 5:
        raise ValueError("No ranching land")
    r = Reader(blob, start - 5)
    out = []
    for _ in range(r.count()):
        land, size = _short(r.text()), r.i32()
        payload = Reader(r.take(size))
        if size < 3 or not payload.flag() or not payload.flag():
            continue
        enclosure = _short(payload.text())
        e = Reader(payload.take(payload.i32()))
        e.flag()
        e.take(12)  # an int32 and two timers, not interpreted
        e.take(8)
        condition = e.f64()
        animals = []
        for _ in range(e.count()):
            species = _short(e.text())
            a = Reader(e.take(e.i32()))
            a.flag()
            gauges = [round(a.f64(), 4) for _ in range(3)]
            a.flag()
            a.i32()
            variant = _short(a.text())
            treats = []
            for _ in range(a.count()):
                flag = a.flag()  # meaning not established (every treat of a save without treats reads False)
                treats.append({"item": _short(a.text()), "flag": flag})
            animals.append({"species": species, "variant": variant, "gauges": gauges, "treats": treats})
        out.append({"land": land, "enclosure": enclosure, "condition": round(condition, 4), "animals": animals})
    return out


def _component(data: bytes, entities: dict, entity: str, name: str):
    if entity not in entities:
        return None
    parts = _table(Reader(data, entities[entity][0]))
    if name not in parts:
        return None
    pos, size = parts[name]
    return data[pos:pos + size]


def _optional(decode, blob, empty):
    """Unknown layouts read as empty rather than failing the whole save (they are not documented)."""
    if blob is None:
        return empty
    try:
        return decode(blob)
    except (ValueError, IndexError, UnicodeDecodeError, struct.error):
        return empty


def parse(data: bytes) -> dict:
    """Decode a decompressed save into plain values."""
    r = Reader(data)
    version = r.i32()
    save = {"version": version, "uuid": str(uuid.UUID(bytes_le=r.take(16))), "name": r.text(), "mode": r.text(),
            "saved_at": saved_at(r.i64())}
    kind, _kind_icon, target, _target_icon = r.text(), r.text(), r.text(), r.text()
    save.update(activity={"kind": kind or None, "target": target or None}, total_level=r.i32(), gp=r.i64(),
                slayer_coins=r.i64(), demo=r.flag())
    entities = _table(r)
    skills = []
    for name, (pos, _) in entities.items():
        exp = _table(Reader(data, pos)).get("Experience")
        if exp and exp[1] in (8, 12):
            x = Reader(data, exp[0])
            xp = x.f64()
            level = x.i32() if exp[1] == 12 else level_for(xp)
            skills.append({"name": _short(name), "level": level, "xp": round(xp, 1)})
    save["skills"] = skills
    save["mastery"] = {}
    for name in entities:
        blob = _component(data, entities, name, "MasteryGuild")
        if blob is not None:
            guild = _optional(_mastery, blob, None)
            if guild:
                save["mastery"][_short(name)] = guild
    save["equipment"] = _optional(_equipment, _component(data, entities, "MelvorBase:Combat", "Equipment"), {})
    save["slayer"] = _optional(_slayer, _component(data, entities, "MelvorBase:Slayer", "Tasks"), {})
    save["farming"] = _optional(_farming, _component(data, entities, "MelvorBase:Farming", "Passive"), {})
    save["ranching"] = _optional(_ranching, _component(data, entities, "MelvorBase:Ranching", "Passive"), [])
    save["astrology"] = {"constellations": [], "active": None}
    if "MelvorBase:Astrology" in entities:
        parts = _table(Reader(data, entities["MelvorBase:Astrology"][0]))
        if "Action" in parts:
            pos, size = parts["Action"]
            save["astrology"] = _astrology(data[pos:pos + size])
    save["bank"], save["wallet"] = {"stacks": 0, "tabs": 0, "items": {}}, {}
    if "MelvorBase:Bank" in entities:
        parts = _table(Reader(data, entities["MelvorBase:Bank"][0]))
        if "Inventory" in parts:
            x = Reader(data, parts["Inventory"][0])
            x.i32()  # default tab for new items
            tabs = x.count()
            stacks, items = 0, {}
            for _ in range(tabs):
                x.take(14)  # three int32 stack limits and two flags
                for _ in range(x.count()):
                    quantity = x.i32()
                    x.take(2)  # two flags; the first is set on real stacks too, so a placeholder is quantity 0
                    item = _short(x.text())
                    if quantity > 0:
                        items[item] = items.get(item, 0) + quantity
                    stacks += 1
                x.text()  # tab label
                for _ in range(x.count()):
                    x.take(2)
                    x.text()  # bank tag
            save["bank"] = {"stacks": stacks, "tabs": tabs, "items": items}
        if "Wallet" in parts:
            w = Reader(data, parts["Wallet"][0])
            for _ in range(w.count()):
                amount = w.i64()
                save["wallet"][_short(w.text())] = amount
    return save


def decompress(raw: bytes) -> bytes:
    # The game leaves its Brotli stream unfinished, so brotli.decompress() refuses it: stream it instead.
    stream, data = brotli.Decompressor(), bytearray()
    for start in range(0, len(raw), 1024):
        data += stream.process(raw[start:start + 1024])
        while not stream.can_accept_more_data():
            data += stream.process(b"")
    return bytes(data)


def load(path) -> dict:
    """Decode one save file, opened read-only."""
    with open(path, "rb") as handle:
        return parse(decompress(handle.read()))
