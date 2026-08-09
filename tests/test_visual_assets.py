from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE.md"


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def _assert_accessible_static_svg(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.attrib["role"] == "img"
    label_ids = root.attrib["aria-labelledby"].split()
    nodes_by_id = {
        node.attrib["id"]: node
        for node in root.iter()
        if node.attrib.get("id")
    }
    assert label_ids
    assert set(label_ids) <= set(nodes_by_id)
    for label_id in label_ids:
        node = nodes_by_id[label_id]
        assert node.tag.endswith(("title", "desc"))
        assert "".join(node.itertext()).strip()
    for node in root.iter():
        for name, value in node.attrib.items():
            if name.endswith("href"):
                assert value.startswith("#"), (name, value)
    for forbidden in ("<script", "<foreignObject", "<animate"):
        assert forbidden not in text
    return text


def test_social_preview_has_exact_github_dimensions_and_budget() -> None:
    path = ASSETS / "agent-frontdoor-social-preview.png"
    assert _png_dimensions(path) == (1280, 640)
    assert path.stat().st_size < 1_000_000


def test_architecture_svg_is_accessible_static_and_exact() -> None:
    text = _assert_accessible_static_svg(
        ASSETS / "agent-frontdoor-architecture.svg"
    )
    for marker in (
        "Task Card",
        "Validation",
        "Drift Detection",
        "Intent Lock",
        "Human Gate",
        "Safe Handoff",
        "Read-only core",
        "Optional adapter",
        "Human authority remains external",
    ):
        assert marker in text


def test_hero_svg_is_accessible_static_and_product_named() -> None:
    text = _assert_accessible_static_svg(
        ASSETS / "agent-frontdoor-hero.svg"
    )
    assert "Agent Frontdoor" in text


def test_architecture_doc_embeds_diagram_with_nonempty_alt_text() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")
    match = re.search(
        r"!\[([^\]]+)\]\(\.\./assets/agent-frontdoor-architecture\.svg\)",
        text,
    )
    assert match
    assert match.group(1).strip()
