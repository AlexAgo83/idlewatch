"""Decoder: header, skills, bank counts and wallet from a synthetic save; damage is explicit."""
import brotli
import pytest

import idlewatch
from synthetic import UUID, astrology, compressed, save, text

EXPECTED = {
    "version": 28, "uuid": UUID, "name": "Tester", "mode": "Test", "saved_at": "2026-01-02T03:04:05Z",
    "activity": {"kind": "Combat", "target": "Treant"}, "total_level": 321, "gp": 12345, "slayer_coins": 678,
    "demo": True, "bank": {"stacks": 5, "tabs": 2, "items": {"Logs": 123, "Ore": 5, "Shrimp": 40}},
    "wallet": {"GoldPieces": 12345, "PrayerPoints": 90, "SlayerCoins": 678},
    "astrology": {"constellations": [], "active": None},
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
