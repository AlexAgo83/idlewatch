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
         uid=UUID, release=False, astrology_action=None) -> bytes:
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
    return header + table(entities)


def compressed(**kwargs) -> bytes:
    return brotli.compress(save(**kwargs))
