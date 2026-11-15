"""The README keeps its short shape: three sections, no subsections, the licence line last."""
import re
from pathlib import Path

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")


def test_shared_sections_in_order_without_subsections():
    assert re.findall(r"(?m)^## (.+)$", README) == ["Get started in a minute", "What you can do", "Documentation"]
    assert re.search(r"(?m)^#{3,} ", README) is None


def test_short_and_ends_with_the_licence_line():
    lines = README.rstrip("\n").split("\n")
    assert len(lines) <= 90
    assert "MIT licensed" in lines[-1]
