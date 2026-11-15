"""CLI: read prints one save, list finds every save under a folder, both read-only."""
import json
import subprocess
import sys
from pathlib import Path

from idlewatch import cli
from synthetic import UUID, compressed


def write_save(root: Path, uid: str = UUID, **kwargs) -> Path:
    path = root / "steam" / "12345" / "saves" / f"save_{uid}.sav"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed(uid=uid, **kwargs))
    return path


def test_read_prints_the_decoded_save(tmp_path, capsys):
    path = write_save(tmp_path)
    before = path.read_bytes()
    assert cli.main(["read", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["uuid"] == UUID
    assert path.read_bytes() == before


def test_read_reports_a_damaged_save(tmp_path, capsys):
    path = tmp_path / "save_bad.sav"
    path.write_bytes(b"not a save")
    assert cli.main(["read", str(path)]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_list_summarises_every_save_and_flags_damaged_ones(tmp_path, capsys):
    other = "99999999-8888-4777-8666-555555555555"
    write_save(tmp_path, name="Tester")
    write_save(tmp_path, uid=other, name="Élise", mode="Hardcore")
    (tmp_path / "steam" / "12345" / "saves" / "save_broken.sav").write_bytes(b"\x00")
    assert cli.main(["list", "--saves-dir", str(tmp_path)]) == 0
    found = json.loads(capsys.readouterr().out)
    assert [(s.get("name"), s.get("mode")) for s in found] == [("Tester", "Test"), ("Élise", "Hardcore"), (None, None)]
    assert found[0]["uuid"] == UUID and found[0]["total_level"] == 321
    assert "error" in found[2]


def test_list_reports_a_missing_folder(tmp_path, capsys):
    assert cli.main(["list", "--saves-dir", str(tmp_path / "missing")]) == 1
    assert "no saves folder" in capsys.readouterr().err


def test_default_saves_dir_per_platform(monkeypatch, tmp_path):
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.setattr(cli.Path, "home", lambda: tmp_path)
    assert cli.default_saves_dir() == tmp_path / "Library" / "Application Support" / "Games By Malcs" / "Melvor Idle 2"
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert cli.default_saves_dir() == tmp_path / "Games By Malcs" / "Melvor Idle 2"
    monkeypatch.setattr(cli.sys, "platform", "linux")
    assert cli.default_saves_dir() is None


def test_module_entry_point_prints_utf8_json(tmp_path):
    path = write_save(tmp_path, name="Élise")
    out = subprocess.run([sys.executable, "-m", "idlewatch", "read", str(path)], capture_output=True, check=True)
    assert json.loads(out.stdout.decode("utf-8"))["name"] == "Élise"
