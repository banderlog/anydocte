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


def test_single_column_csv_is_sniffed_as_plain_text(sniff, monkeypatch):
    """libmagic needs a delimiter to say `text/csv`.

    A one-column file is reported `text/plain`, so it takes the Native Text
    path rather than anydoc. Content is preserved, just not tabulated. Pinned
    so the behaviour is not mistaken for a regression.
    """
    sniff("text/plain")

    def unexpected(data, fmt=None, **kw):
        raise AssertionError("single-column CSV must not reach anydoc")

    monkeypatch.setattr(anydoc, "to_markdown_bytes", unexpected)
    assert extractors.extract(b"name\nbolt\nnut\n", SETTINGS) == (
        "name\nbolt\nnut\n",
        "Native Text",
    )


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


@pytest.mark.parametrize(
    "mime",
    [
        "application/vnd.ms-excel",  # -> ".xls"
        "application/x-ole-storage",  # generic OLE2, guess_extension -> None
    ],
)
def test_legacy_xls_and_bare_ole2_are_unsupported(mime, sniff):
    """`.xls` must NOT reach anydoc, which has no such format.

    anydoc supports doc/ppt but not xls (`unknown format "xls"`), and
    autodetect on OLE2 bytes raises `UnsupportedError` — so routing these to
    it would turn a clean empty result into an HTTP 500. Pinned so a
    well-meaning "add .xls support" change fails here, not in production.
    Contrast `.doc`/`.ppt`, which anydoc does support and which therefore
    route to it (and correctly propagate a 500 when genuinely malformed).
    """
    sniff(mime)
    content, method = extractors.extract(b"\xd0\xcf\x11\xe0garbage", SETTINGS)
    assert method == "Unsupported filetype"
    assert content == ""


@pytest.mark.parametrize(
    "mime", ["application/msword", "application/vnd.ms-powerpoint"]
)
def test_legacy_doc_and_ppt_do_reach_anydoc(mime, sniff, monkeypatch):
    """The counterpart: doc/ppt ARE anydoc formats, so they must be routed."""
    sniff(mime)
    monkeypatch.setattr(anydoc, "to_markdown_bytes", lambda data, *a, **kw: "<legacy>")
    assert extractors.extract(b"\xd0\xcf\x11\xe0x", SETTINGS) == (
        "<legacy>",
        "Anydoc Native",
    )


def test_anydoc_receives_no_explicit_format_for_office(sniff, monkeypatch):
    """Office types rely on anydoc's own sniffing; only CSV names a format.

    Asserts the real call shape rather than swallowing any args, so a
    signature regression cannot hide behind a permissive fake.
    """
    sniff("application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    seen = {}

    def fake(data, fmt=None, **kw):
        seen["data"] = data
        seen["fmt"] = fmt
        seen["kw"] = kw
        return "<office>"

    monkeypatch.setattr(anydoc, "to_markdown_bytes", fake)
    assert extractors.extract(b"PK\x03\x04", SETTINGS) == ("<office>", "Anydoc Native")
    assert seen["fmt"] is None, "office paths must not pass an explicit format"
    assert seen["kw"] == {}
    assert seen["data"] == b"PK\x03\x04"


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
