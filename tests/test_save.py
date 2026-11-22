"""Decoder: header, skills, bank counts and wallet from a synthetic save; damage is explicit."""
import brotli
import pytest

import idlewatch
from synthetic import (
    UUID,
    astrology,
    compressed,
    equipped,
    guild_task,
    plot,
    quest,
    ranch_animal,
    ranching,
    records,
    save,
    slayer_task,
    text,
)

EXPECTED = {
    "version": 28, "uuid": UUID, "name": "Tester", "mode": "Test", "saved_at": "2026-01-02T03:04:05Z",
    "activity": {"kind": "Combat", "target": "Treant"}, "total_level": 321, "gp": 12345, "slayer_coins": 678,
    "demo": True, "bank": {"stacks": 5, "tabs": 2, "items": {"Logs": 123, "Ore": 5, "Shrimp": 40}},
    "wallet": {"GoldPieces": 12345, "PrayerPoints": 90, "SlayerCoins": 678},
    "astrology": {"constellations": [], "active": None},
    "mastery": {}, "equipment": {}, "loadouts": {}, "slayer": {}, "farming": {}, "ranching": [], "quests": {},
    "skills": [{"name": "Mining", "level": 20, "xp": 1000.5}, {"name": "Fishing", "level": 25, "xp": 2500.0},
               {"name": "Thieving", "level": 15, "xp": 750.2}, {"name": "Attack", "level": 30, "xp": 4000.0}]}


def test_synthetic_save_decodes(tmp_path):
    path = tmp_path / "save.sav"
    path.write_bytes(compressed())
    assert idlewatch.load(path) == EXPECTED


def test_unfinished_brotli_stream_still_decodes(tmp_path):
    # The game never finishes its stream: drop the final empty meta-block a complete stream ends with.
    stream = brotli.Compressor()
    path = tmp_path / "save.sav"
    path.write_bytes(stream.process(save()) + stream.flush())
    with pytest.raises(brotli.error):
        brotli.decompress(path.read_bytes())
    assert idlewatch.load(path)["name"] == "Tester"


@pytest.mark.parametrize("cut", [10, 60, -5])
def test_truncated_save_is_an_error(cut):
    with pytest.raises(ValueError):
        idlewatch.parse(save()[:cut])


def test_long_names_use_multibyte_lengths():
    assert idlewatch.parse(save(name="É" * 100))["name"] == "É" * 100


def test_a_save_without_skills_still_has_empty_sections():
    decoded = idlewatch.parse(save(skills=()))
    assert decoded["skills"] == [] and decoded["bank"]["stacks"] == 5


def test_release_saves_keep_the_xp_and_the_level_comes_from_the_curve(tmp_path):
    path = tmp_path / "save.sav"
    skills = [("Woodcutting", 71077.0, 0), ("Mining", 270726.7, 0), ("Firemaking", 35563.0, 0)]
    path.write_bytes(compressed(release=True, demo=False, skills=skills))
    assert idlewatch.load(path)["skills"] == [{"name": "Woodcutting", "level": 46, "xp": 71077.0},
                                              {"name": "Mining", "level": 59, "xp": 270726.7},
                                              {"name": "Firemaking", "level": 39, "xp": 35563.0}]


def test_the_curve_matches_the_known_thresholds():
    from idlewatch.save import level_for
    assert [level_for(x) for x in (0, 82, 83, 13362, 13363, 13034430, 13034431)] == [1, 1, 2, 29, 30, 98, 99]


@pytest.mark.parametrize("header", [b"", b"\0", b"\x01\0\0\0\0"])
def test_astrology_constellations_with_nodes(tmp_path, header):
    nodes = ["DeedreeA1", "DeedreeA2", "DeedreeB1", "DeedreeC1", "DeedreeD1", "DeedreeD2"]
    action = astrology([("Deedree", 234, 10732.1, nodes, ["DeedreeMajor1"]),
                        ("Iridan", 12, 321.5, ["IridanA1"], ["IridanMajor1", "IridanMajor2"]),
                        ("Ameria", 0, 0.0, [], [])], active="Iridan", header=header)
    data = save(release=True, demo=False, astrology_action=action)
    expected = {"constellations": [
        {"id": "Deedree", "value": 234, "xp": 10732.1, "minor": nodes, "major": ["DeedreeMajor1"]},
        {"id": "Iridan", "value": 12, "xp": 321.5, "minor": ["IridanA1"],
         "major": ["IridanMajor1", "IridanMajor2"]},
        {"id": "Ameria", "value": 0, "xp": 0.0, "minor": [], "major": []}], "active": "Iridan"}
    assert idlewatch.parse(data)["astrology"] == expected
    path = tmp_path / "astrology.sav"
    path.write_bytes(brotli.compress(data))
    decoded = idlewatch.load(path)
    assert decoded["astrology"] == expected
    assert decoded["bank"] == EXPECTED["bank"]


def test_astrology_without_purchased_nodes():
    action = astrology([("Deedree", 234, 10732.1, [], []), ("Iridan", 0, 0.0, [], [])], "Deedree")
    assert idlewatch.parse(save(astrology_action=action))["astrology"] == {
        "constellations": [{"id": "Deedree", "value": 234, "xp": 10732.1, "minor": [], "major": []},
                           {"id": "Iridan", "value": 0, "xp": 0.0, "minor": [], "major": []}],
        "active": "Deedree"}


@pytest.mark.parametrize("action", [None, False, astrology([])])
def test_missing_or_empty_astrology(action):
    assert idlewatch.parse(save(astrology_action=action))["astrology"] == {"constellations": [], "active": None}


@pytest.mark.parametrize("action", [
    b"unknown layout", b"\xff" * 32,
    astrology([("Deedree", 1, 2.0, [], [])], "Deedree")[:-1],
    astrology([("Deedree", 1, 2.0, [], [])], "Deedree") + b"extra",
    astrology([("Deedree", 1, float("nan"), [], [])], "Deedree"),
    astrology([("Deedree", 1, 2.0, [], [])], "Iridan"),
    astrology([("Deedree", 1, 2.0, [], [])], "Deedree").replace(text("MelvorBase:Deedree"), b"\xff", 1),
])
def test_unknown_astrology_layout_does_not_break_loading(tmp_path, action):
    path = tmp_path / "unknown-astrology.sav"
    path.write_bytes(compressed(astrology_action=action))
    decoded = idlewatch.load(path)
    assert decoded["astrology"] == {"constellations": [], "active": None}
    assert decoded["bank"] == EXPECTED["bank"]
    assert decoded["wallet"] == EXPECTED["wallet"]


@pytest.mark.parametrize("active", ["Arachi", ""])
def test_astrology_flagged_active_tail(active):
    """Later release saves: a presence flag before the active id and two zero bytes after it (2026-11)."""
    action = astrology([("Deedree", 234, 10732.1, ["DeedreeA1"], ["DeedreeMajor1"]), ("Arachi", 16, 50.0, [], [])],
                       active, header=b"\0\x01\0\0\0\0\xb4\0\0\0\0\0\0\0\x01\x01", flagged=True)
    decoded = idlewatch.parse(save(release=True, demo=False, astrology_action=action))["astrology"]
    assert [c["id"] for c in decoded["constellations"]] == ["Deedree", "Arachi"]
    assert decoded["active"] == (active or None)


def test_astrology_unknown_tail_is_not_misread():
    action = astrology([("Deedree", 234, 10732.1, [], [])], "Deedree", flagged=True) + b"\x07"
    assert idlewatch.parse(save(release=True, demo=False, astrology_action=action))["astrology"] == {
        "constellations": [], "active": None}


def test_equipment_mastery_slayer_and_farming():
    """Equipped items, mastery guild tasks, Slayer tasks per master and crops per plot (release layouts)."""
    import struct
    extra = {
        "MelvorBase:Combat": {"Equipment": records(
            [("Helmet", equipped("MithrilHelmetU")), ("Ammo", equipped(None)),
             ("Quiver", equipped("BronzeArrows", 250))],
            tail=records([
                ("Loadout2", records([
                    ("Helmet", equipped("ChainmailCowlU")), ("Ammo", equipped("SapphireBolts", 463)),
                ])),
                ("Loadout3", records([("Weapon", equipped("WaterBattlewand")), ("Boots", equipped(None))])),
            ]))},
        "MelvorBase:Woodcutting": {"Experience": struct.pack("<d", 100.0),
                                   "MasteryGuild": b"\x01" + text("MelvorBase:Novice") + records(
                                       [("WoodcuttingTask1", guild_task(200.0, True)),
                                        ("WoodcuttingTask2", guild_task(2297.0)),
                                        ("WoodcuttingTask3", guild_task(None)),
                                        ("WoodcuttingTask4", guild_task(0.0))])},
        "MelvorBase:Slayer": {"Tasks": records([("Kuren", slayer_task("MagicCow", 31, 14, ["EvilPlant"])),
                                                ("Hans", slayer_task("GasBall", 211)), ("Zaos", slayer_task(None))],
                                               tail=b"\x01" + text("MelvorBase:Hans"))},
        # Clock 73120538 (1/60 s); Allotment1's Potato is ready 117600 ticks later, Herb1's Nomel tick passed.
        "MelvorBase:Farming": {"Passive": b"\x01" + text("MelvorBase:Trees") + struct.pack("<q", 73120538)
                               + records([("Allotment1", plot("Onion", True, ("Potato", 324000, 73238138))),
                                          ("Herb1", plot("NomelHerb", growing=("NomelHerb", 1080000, 73000000))),
                                          ("Tree1", plot("WillowTree", True)), ("Tree2", plot(None))])},
    }
    decoded = idlewatch.parse(save(release=True, demo=False, extra=extra))
    assert decoded["equipment"] == {"Helmet": {"item": "MithrilHelmetU", "quantity": 1},
                                    "Quiver": {"item": "BronzeArrows", "quantity": 250}}
    assert decoded["loadouts"] == {"Loadout2": {"Helmet": {"item": "ChainmailCowlU", "quantity": 1},
                                                "Ammo": {"item": "SapphireBolts", "quantity": 463}},
                                   "Loadout3": {"Weapon": {"item": "WaterBattlewand", "quantity": 1}}}
    assert decoded["mastery"] == {"Woodcutting": {
        "done": ["WoodcuttingTask1"], "progress": {"WoodcuttingTask2": 2297.0}, "untouched": 1}}
    assert decoded["slayer"] == {
        "Kuren": {"monster": "MagicCow", "counters": [31, 14], "active": False, "blocked": ["EvilPlant"]},
        "Hans": {"monster": "GasBall", "counters": [211, 0], "active": True, "blocked": []}}
    assert decoded["farming"] == {
        "Allotment1": {"crop": "Onion", "fertilised": True,
                       "growing": {"crop": "Potato", "seconds": 5400, "remaining": 1960}},
        "Herb1": {"crop": "NomelHerb", "fertilised": False,
                  "growing": {"crop": "NomelHerb", "seconds": 18000, "remaining": 0}},
        "Tree1": {"crop": "WillowTree", "fertilised": True, "growing": None}}


def test_unknown_component_layouts_read_as_empty():
    extra = {"MelvorBase:Combat": {"Equipment": b"\x05\0\0\0junk"}, "MelvorBase:Slayer": {"Tasks": b"\xff" * 3}}
    decoded = idlewatch.parse(save(extra=extra))
    assert (
        decoded["equipment"] == {} and decoded["loadouts"] == {} and decoded["slayer"] == {}
        and decoded["skills"] == EXPECTED["skills"]
    )


def test_ranching_land_enclosures_and_animals():
    sheep = [ranch_animal("Sheep", "SheepAdult"), ranch_animal("Sheep", "SheepChild", (0.5, 1.0, 0.3))]
    chicken = ranch_animal("Chicken", "ChickenAdult", treats=("Corn", "Mealworm"))
    blob = ranching([("Land1", "CowSheepEnclosureII", sheep), ("Land2", None, []),
                     ("Land3", "ChickenCoopIII", [chicken])])
    extra = {"MelvorBase:Ranching": {"Passive": blob}}
    decoded = idlewatch.parse(save(release=True, demo=False, extra=extra))["ranching"]
    assert [(land["land"], land["enclosure"], land["condition"], len(land["animals"])) for land in decoded] == [
        ("Land1", "CowSheepEnclosureII", 0.99, 2), ("Land3", "ChickenCoopIII", 0.99, 1)]
    assert decoded[0]["animals"][1] == {"species": "Sheep", "variant": "SheepChild", "gauges": [0.5, 1.0, 0.3],
                                        "hunger": 0.5, "comfort": 1.0, "satisfaction": 0.3,
                                        "treats": [{"item": "Apple", "flag": False}],
                                        "adult_in_minutes": -6807, "lifespan_minutes": 105}
    assert [t["item"] for t in decoded[1]["animals"][0]["treats"]] == ["Corn", "Mealworm"]
    garbled = {"MelvorBase:Ranching": {"Passive": b"\x01MelvorBase:Land1 junk"}}
    assert idlewatch.parse(save(extra=garbled))["ranching"] == []


def test_quests_status_and_current_step():
    """Status 3 complete, 1 active (its first unfinished step's tasks and goal progress), 0 not started."""
    blob = records([("MQ1", quest(3, [(True, [({"0": 3.0}, True)])])),
                    ("MQ7", quest(1, [(True, [({}, True)]), (False, [({"0": 0.0}, False)]),
                                      (False, [({"0": 0.0}, False), ({"0": 0.0}, False)])])),
                    ("MQ8", quest(0, [(False, [({"0": 0.0, "1": 0.0}, False)])]))], tail=b"\0\0")
    decoded = idlewatch.parse(save(extra={"MelvorBase:Quests": {"Quests": blob}}))["quests"]
    assert decoded == {
        "MQ1": {"status": "complete", "steps_done": 1, "steps": 1, "step": None, "tasks": []},
        "MQ7": {"status": "active", "steps_done": 1, "steps": 3, "step": "1",
                "tasks": [{"task": "0", "done": False, "goals": {"0": 0.0}}]},
        "MQ8": {"status": "not_started", "steps_done": 0, "steps": 1, "step": None, "tasks": []}}
    assert idlewatch.parse(save(extra={"MelvorBase:Quests": {"Quests": b"\x01\0\0\0junk"}}))["quests"] == {}
