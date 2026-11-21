"""Synthetic Melvor Idle 2 save, written in the game's .NET BinaryWriter layout then Brotli-compressed."""
import datetime
import struct
import uuid

import brotli

UUID = "11111111-2222-4333-8444-555555555555"
SKILLS = (("Mining", 1000.5, 20), ("Fishing", 2500.0, 25), ("Thieving", 750.25, 15), ("Attack", 4000.0, 30))


def text(value: str) -> bytes:
    raw = value.encode()
    n, out = len(raw), bytearray()
    while n >= 0x80:
        out.append(n & 0x7F | 0x80)
        n >>= 7
    return bytes(out) + bytes([n]) + raw


def table(entries: dict[str, bytes]) -> bytes:
    return struct.pack("<i", len(entries)) + b"".join(text(k) + struct.pack("<i", len(v)) + v
                                                      for k, v in entries.items())


def tab(label: str, items) -> bytes:
    return (struct.pack("<iii??", 0, 0, 0, False, False) + struct.pack("<i", len(items))
            + b"".join(struct.pack("<i??", n, held, False) + text(f"MelvorBase:{i}") for i, n, held in items)
            + text(label) + struct.pack("<i", 1) + struct.pack("<??", True, False) + text("tag"))


def astrology(constellations, active="", header=b"\0", flagged=False) -> bytes:
    """Build an Action blob with an opaque header and length-prefixed constellation records."""
    out = header + struct.pack("<i", len(constellations))
    for name, value, xp, minor, major in constellations:
        out += text(f"MelvorBase:{name}") + struct.pack("<id", value, xp)
        for nodes in (minor, major):
            out += struct.pack("<i", len(nodes)) + b"".join(text(f"MelvorBase:{node}") for node in nodes)
    if flagged:  # later release saves: presence flag, the id when set, two zero bytes
        return out + (b"\x01" + text(f"MelvorBase:{active}") if active else b"\0") + b"\0\0"
    return out + text(f"MelvorBase:{active}" if active else "")


def save(name="Tester", mode="Test", demo=True, at=datetime.datetime(2026, 1, 2, 3, 4, 5), skills=SKILLS,
         uid=UUID, release=False, astrology_action=None, extra=None) -> bytes:
    ticks = (at - datetime.datetime(1, 1, 1)) // datetime.timedelta(microseconds=1) * 10
    header = (struct.pack("<i", 28) + uuid.UUID(uid).bytes_le + text(name) + text(mode)
              + struct.pack("<q", (ticks | 1 << 63) - (1 << 64))  # DateTimeKind.Local, as ToBinary writes it
              + text("Combat") + text("res://Assets/Icons/Combat.png") + text("Treant")
              + text("res://Assets/Monsters/Treant.png") + struct.pack("<iqq?", 321, 12345, 678, demo))
    inventory = (struct.pack("<ii", 0, 2) + tab("Main", [("Logs", 120, True), ("Ore", 5, False), ("Bones", 0, True)])
                 + tab("Food", [("Shrimp", 40, False), ("Logs", 3, False)]))
    wallet = struct.pack("<i", 3) + b"".join(struct.pack("<q", amount) + text(f"MelvorBase:{k}") for k, amount in
                                             (("GoldPieces", 12345), ("PrayerPoints", 90), ("SlayerCoins", 678)))
    entities = {"MelvorBase:OfflineProgress": table({"State": b"\x01\x02"}),
                "MelvorBase:Bank": table({"Inventory": inventory, "Wallet": wallet})}
    for skill, xp, level in skills:
        # The release keeps the xp only; the demo also stored the level.
        experience = struct.pack("<d", xp) if release else struct.pack("<di", xp, level)
        entities[f"MelvorBase:{skill}"] = table({"Mastery": b"\0" * 7, "Experience": experience})
    if astrology_action is not None:
        parts = {"Experience": struct.pack("<d", 1000.0)}
        if astrology_action is not False:
            parts["Action"] = astrology_action
        entities["MelvorBase:Astrology"] = table(parts)
    for entity, parts in (extra or {}).items():
        entities[entity] = table(parts)
    return header + table(entities)


def compressed(**kwargs) -> bytes:
    return brotli.compress(save(**kwargs))


def record(name: str, payload: bytes) -> bytes:
    return text(f"MelvorBase:{name}") + struct.pack("<i", len(payload)) + payload


def records(items: list[tuple[str, bytes]], tail: bytes = b"") -> bytes:
    return struct.pack("<i", len(items)) + b"".join(record(n, p) for n, p in items) + tail


def equipped(item: str | None, quantity: int = 1) -> bytes:
    if item is None:
        return struct.pack("<i??", -1, False, False)
    return struct.pack("<i??", quantity, False, True) + text(f"MelvorBase:{item}")


def guild_task(progress: float | None, done: bool = False) -> bytes:
    """A mastery guild task: untouched (2 bytes) or with a goal key, its progress and three flags."""
    if progress is None:
        return b"\0\x01"
    return b"\x01" + text("0") + struct.pack("<id", 10, progress) + struct.pack("<???", done, not done, True)


def slayer_task(monster: str | None, first: int = 0, second: int = 0, blocked=()) -> bytes:
    head = (b"\x01" + text(f"MelvorBase:{monster}") + struct.pack("<ii", first, second)) if monster else b"\0" * 11
    blocks = b"".join(text(f"Block{i}") + struct.pack("<i", 2 + len(text(f"MelvorBase:{m}"))) + b"\x01\x01"
                      + text(f"MelvorBase:{m}") for i, m in enumerate(blocked, 1))
    return head + b"\0\x01" + struct.pack("<i", len(blocked)) + blocks


def plot(crop: str | None, fertiliser: bool = False, growing: tuple | None = None) -> bytes:
    """A farming plot as the release writes it: five flags, the chosen crop, two item slots, a state, then for a
    growing plot (state 2) the growing crop, a flag, an int32, the growth time and the ready tick (1/60 s)."""
    if crop is None:
        return b"\0" * 12
    slot = b"\x01" + text("MelvorBase:Fertiliser") if fertiliser else b"\0"
    out = b"\x01" * 5 + b"\x01" + text(f"MelvorBase:{crop}") + slot + slot
    if growing is None:
        return out + struct.pack("<i", 1)
    name, duration, ready = growing
    return (out + struct.pack("<i", 2) + text(f"MelvorBase:{name}") + b"\0"
            + struct.pack("<iii", 2, duration, ready) + b"\0" * 8)


def quest(status: int, steps) -> bytes:
    """A quest record: status, then steps; each step holds tasks (goal id -> progress, done) and a step status."""
    out = struct.pack("<ii", status, len(steps))
    for step_id, (step_done, tasks) in enumerate(steps):
        body = struct.pack("<i", len(tasks))
        for task_id, (goals, task_done) in enumerate(tasks):
            task = struct.pack("<i", len(goals)) + b"".join(
                text(g) + struct.pack("<i", 10) + struct.pack("<d??", v, task_done, not task_done)
                for g, v in goals.items())
            task += b"\x01\x01\x01" + struct.pack("<i", 2 if task_done else 1)
            body += text(str(task_id)) + struct.pack("<i", len(task)) + task
        body += b"\x01" + struct.pack("<i", 2 if step_done else 0)
        out += text(str(step_id)) + struct.pack("<i", len(body)) + body
    return out


def ranch_animal(species: str, variant: str, gauges=(1.0, 0.99, 0.94), treats=("Apple",)) -> bytes:
    body = (b"\0" + struct.pack("<ddd", *gauges) + b"\0" + struct.pack("<i", 13) + text(f"MelvorBase:{variant}")
            + struct.pack("<i", len(treats)) + b"".join(b"\0" + text(f"MelvorBase:{t}") for t in treats)
            + struct.pack("<ddd", 105, -6807, 2060))
    return text(f"MelvorBase:{species}") + struct.pack("<i", len(body)) + body


def ranching(lands) -> bytes:
    """Ranching Passive: an opaque header, then land records; a used land holds an enclosure with its animals."""
    out = b"\0\x02\0\0\0" + b"\0" * 20 + struct.pack("<i", len(lands))
    for land, enclosure, animals in lands:
        if enclosure is None:
            payload = b"\0\0"
        else:
            enc = (b"\x01" + struct.pack("<iii", 2, 216000, 72160156) + b"\0" * 8 + struct.pack("<d", 0.99)
                   + struct.pack("<i", len(animals)) + b"".join(animals) + struct.pack("<i", 0))
            payload = b"\x01\x01" + text(f"MelvorBase:{enclosure}") + struct.pack("<i", len(enc)) + enc
        out += text(f"MelvorBase:{land}") + struct.pack("<i", len(payload)) + payload
    return out + b"tail"
