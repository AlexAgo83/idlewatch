"""Decoder: header, skills, bank counts and wallet from a synthetic save; damage is explicit."""
import brotli
import pytest

import idlewatch
from synthetic import UUID, compressed, save

EXPECTED = {
    "version": 28, "uuid": UUID, "name": "Tester", "mode": "Test", "saved_at": "2026-01-02T03:04:05Z",
    "activity": {"kind": "Combat", "target": "Treant"}, "total_level": 321, "gp": 12345, "slayer_coins": 678,
    "demo": True, "bank": {"stacks": 5, "tabs": 2, "items": {"Logs": 123, "Ore": 5, "Shrimp": 40}},
    "wallet": {"GoldPieces": 12345, "PrayerPoints": 90, "SlayerCoins": 678},
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
    path.write_bytes(compressed(release=True, demo=False,
                                skills=[("Woodcutting", 71077.0, 0), ("Mining", 270726.7, 0), ("Firemaking", 35563.0, 0)]))
    assert idlewatch.load(path)["skills"] == [{"name": "Woodcutting", "level": 46, "xp": 71077.0},
                                              {"name": "Mining", "level": 59, "xp": 270726.7},
                                              {"name": "Firemaking", "level": 39, "xp": 35563.0}]


def test_the_curve_matches_the_known_thresholds():
    from idlewatch.save import level_for
    assert [level_for(x) for x in (0, 82, 83, 13362, 13363, 13034430, 13034431)] == [1, 1, 2, 29, 30, 98, 99]
