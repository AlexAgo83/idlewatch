"""Read-only decoder for Melvor Idle 2 saves (a Brotli stream holding a .NET BinaryWriter layout).

A save starts with a header (character, mode, time, current activity, totals), then a table of
entities, each a table of components. Skills are entities with a 12-byte Experience component
(float64 xp, int32 level); the bank is MelvorBase:Bank with Inventory and Wallet components. Bank items
are kept by short name with their quantity; placeholders (stacks with quantity 0) are left out.
"""
from __future__ import annotations

import datetime
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


def _short(name: str) -> str:
    return name.split(":", 1)[-1]


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
        if exp and exp[1] == 12:
            x = Reader(data, exp[0])
            xp = x.f64()
            skills.append({"name": _short(name), "level": x.i32(), "xp": round(xp, 1)})
    save["skills"] = skills
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
