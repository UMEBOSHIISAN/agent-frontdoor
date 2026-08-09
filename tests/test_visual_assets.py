from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zlib


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ARCHITECTURE = ROOT / "docs" / "ARCHITECTURE.md"


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return struct.unpack(">II", data[16:24])


def _png_chunks(path: Path) -> tuple[tuple[bytes, bytes], ...]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks = []
    offset = 8
    while offset < len(data):
        assert offset + 12 <= len(data)
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload_end = offset + 8 + length
        crc_end = payload_end + 4
        assert crc_end <= len(data)
        payload = data[offset + 8 : payload_end]
        expected_crc = struct.unpack(">I", data[payload_end:crc_end])[0]
        assert zlib.crc32(chunk_type + payload) & 0xFFFFFFFF == expected_crc
        chunks.append((chunk_type, payload))
        offset = crc_end
        if chunk_type == b"IEND":
            break
    assert chunks and chunks[-1][0] == b"IEND"
    assert offset == len(data)
    return tuple(chunks)


def _png_xmp(path: Path) -> str:
    for chunk_type, payload in _png_chunks(path):
        if chunk_type != b"iTXt":
            continue
        keyword, remainder = payload.split(b"\0", 1)
        if keyword != b"XML:com.adobe.xmp":
            continue
        compression_flag, compression_method = remainder[:2]
        remainder = remainder[2:]
        _language, remainder = remainder.split(b"\0", 1)
        _translated_keyword, text = remainder.split(b"\0", 1)
        assert compression_method == 0
        if compression_flag == 1:
            text = zlib.decompress(text)
        else:
            assert compression_flag == 0
        return text.decode("utf-8")
    raise AssertionError("PNG has no Adobe XMP iTXt chunk")


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


def test_social_preview_xmp_dimensions_match_ihdr() -> None:
    path = ASSETS / "agent-frontdoor-social-preview.png"
    xmp = ET.fromstring(_png_xmp(path))
    exif = "{http://ns.adobe.com/exif/1.0/}"
    x_dimension = xmp.find(f".//{exif}PixelXDimension")
    y_dimension = xmp.find(f".//{exif}PixelYDimension")
    assert x_dimension is not None and x_dimension.text == "1280"
    assert y_dimension is not None and y_dimension.text == "640"


def test_architecture_svg_is_accessible_static_and_exact() -> None:
    path = ASSETS / "agent-frontdoor-architecture.svg"
    text = _assert_accessible_static_svg(path)
    root = ET.fromstring(text)
    assert root.attrib["viewBox"] == "0 0 1280 720"
    rendered_text = " ".join(" ".join(root.itertext()).split())
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
        "Three independent primitives",
        "Maps supported lifecycle events to Intent Lock only",
    ):
        assert marker in rendered_text
    assert "marker-end" not in text
    assert ">01<" not in text
    assert ">02<" not in text
    assert ">03<" not in text
    assert ">04<" not in text


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
