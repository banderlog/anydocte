"""Dispatch routing tests.

Per CONSTITUTION.md rule 5 these must not touch the real OCR stack: the
concrete extractors are monkeypatched, and the libmagic sniff is stubbed so
the routing table can be exercised without crafting real fixture files.
"""

import io

import anydoc
import pytest

import anydocte.extractors as extractors
from anydocte.config import Settings
from anydocte.extractors import image, pdf

SETTINGS = Settings(max_workers=1, tesseract_config="-l eng", pdf_dpi=150)

IMAGE_MIMES = [
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
]

ANYDOC_MIMES = [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/msword",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/rtf",
    "application/epub+zip",
]


@pytest.fixture()
def sniff(monkeypatch):
    """Force the libmagic sniff to report a chosen MIME type."""

    def _set(mime: str) -> None:
        monkeypatch.setattr(
            extractors.magic, "from_buffer", lambda data, mime=True, _m=mime: _m
        )

    return _set


@pytest.mark.parametrize("mime", IMAGE_MIMES)
def test_image_mimes_route_to_ocr(mime, sniff, monkeypatch):
    sniff(mime)
    monkeypatch.setattr(image, "extract", lambda data, s: "<img>")
    assert extractors.extract(b"x", SETTINGS) == ("<img>", "Image OCR")


def test_pdf_routes_to_pdf_extractor(sniff, monkeypatch):
    sniff("application/pdf")
    monkeypatch.setattr(pdf, "extract", lambda data, s: "<pdf>")
    assert extractors.extract(b"x", SETTINGS) == ("<pdf>", "PDF Inspector / OCR")


@pytest.mark.parametrize("mime", ANYDOC_MIMES)
def test_anydoc_mimes_route_to_anydoc(mime, sniff, monkeypatch):
    sniff(mime)
    monkeypatch.setattr(anydoc, "to_markdown_bytes", lambda data, *a, **kw: "<office>")
    assert extractors.extract(b"x", SETTINGS) == ("<office>", "Anydoc Native")


def test_csv_passes_explicit_format_to_anydoc(sniff, monkeypatch):
    """anydoc cannot sniff a bare CSV, so the format must be passed through."""
    sniff("text/csv")
    seen = {}

    def fake(data, fmt=None, **kw):
        seen["fmt"] = fmt
        return "<csv>"

    monkeypatch.setattr(anydoc, "to_markdown_bytes", fake)
    assert extractors.extract(b"a,b\n1,2\n", SETTINGS) == ("<csv>", "Anydoc Native")
    assert seen["fmt"] == "csv"


def test_corrupt_csv_falls_back_to_plain_text(sniff, monkeypatch):
    """A CSV anydoc cannot parse is still ingested, as plain text."""
    sniff("text/csv")

    def boom(data, fmt=None, **kw):
        raise ValueError("record 2: wrong number of fields")

    monkeypatch.setattr(anydoc, "to_markdown_bytes", boom)
    content, method = extractors.extract(b"a,b,c\n1,2\n", SETTINGS)
    assert method == "Native Text (CSV fallback)"
    assert content == "a,b,c\n1,2\n"


def test_corrupt_csv_fallback_survives_bad_utf8(sniff, monkeypatch):
    """The fallback must not trade a CSV error for a decode error."""
    sniff("text/csv")

    def boom(data, fmt=None, **kw):
        raise ValueError("parse error")

    monkeypatch.setattr(anydoc, "to_markdown_bytes", boom)
    content, method = extractors.extract(b"a,b\n1,\xff\xfe\n", SETTINGS)
    assert method == "Native Text (CSV fallback)"
    assert "a,b" in content


def test_csv_fallback_is_logged(sniff, monkeypatch, caplog):
    sniff("text/csv")

    def boom(data, fmt=None, **kw):
        raise ValueError("ragged rows")

    monkeypatch.setattr(anydoc, "to_markdown_bytes", boom)
    with caplog.at_level("WARNING", logger="extractor-proxy"):
        extractors.extract(b"a,b\n1\n", SETTINGS)
    assert "anydoc failed to parse CSV (ragged rows)" in caplog.text


def test_healthy_csv_does_not_use_fallback(sniff, monkeypatch):
    """The happy path must stay on anydoc, not silently degrade."""
    sniff("text/csv")
    monkeypatch.setattr(anydoc, "to_markdown_bytes", lambda data, *a, **kw: "| a |")
    assert extractors.extract(b"a\n1\n", SETTINGS) == ("| a |", "Anydoc Native")


def test_non_csv_anydoc_failure_still_propagates(sniff, monkeypatch):
    """The fallback is CSV-only: a broken docx must still surface as a 500."""
    sniff("application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    def boom(data, fmt=None, **kw):
        raise ValueError("corrupt zip")

    monkeypatch.setattr(anydoc, "to_markdown_bytes", boom)
    with pytest.raises(ValueError, match="corrupt zip"):
        extractors.extract(b"PK\x03\x04junk", SETTINGS)


def test_plain_text_is_decoded_natively(sniff):
    sniff("text/plain")
    assert extractors.extract(b"hello world", SETTINGS) == ("hello world", "Native Text")


def test_text_subtype_without_extension_falls_back_to_native_text(sniff):
    """text/* with no mimetypes extension still decodes instead of failing."""
    sniff("text/x-shellscript")
    assert extractors.extract(b"#!/bin/sh\n", SETTINGS) == (
        "#!/bin/sh\n",
        "Native Text",
    )


def test_invalid_utf8_is_replaced_not_raised(sniff):
    sniff("text/plain")
    content, method = extractors.extract(b"ok \xff\xfe bad", SETTINGS)
    assert method == "Native Text"
    assert "ok " in content


def test_unknown_binary_is_unsupported(sniff):
    sniff("application/octet-stream")
    assert extractors.extract(b"\x00\x01garbage", SETTINGS) == (
        "",
        "Unsupported filetype",
    )


def test_settings_passed_through(sniff, monkeypatch):
    sniff("image/png")
    captured = {}

    def fake(data, s):
        captured["s"] = s
        return "ok"

    monkeypatch.setattr(image, "extract", fake)
    assert extractors.extract(b"x", SETTINGS) == ("ok", "Image OCR")
    assert captured["s"] is SETTINGS


def test_real_png_bytes_route_by_content(monkeypatch):
    """Routing is content-based: real PNG bytes need no filename hint.

    This uses the real libmagic sniff (cheap, no OCR) but stubs the extractor,
    so it stays within the no-OCR tier of CONSTITUTION.md rule 5.
    """
    from PIL import Image as PILImage

    monkeypatch.setattr(image, "extract", lambda data, s: "<img>")
    buf = io.BytesIO()
    PILImage.new("L", (8, 8), 255).save(buf, format="PNG")
    assert extractors.extract(buf.getvalue(), SETTINGS) == ("<img>", "Image OCR")
