"""Full-pipeline tests against the real OCR stack (CONSTITUTION.md, rule 5)."""

import io
import time

from PIL import Image, ImageDraw, ImageFont

from anydocte.config import DEFAULT_TESSERACT_CONFIG, Settings
from anydocte.extractors import extract

EXPECTED = "ANYDOCTE 12345"


def _make_image(text: str) -> Image.Image:
    font = ImageFont.load_default(size=64)
    probe = Image.new("L", (1, 1))
    left, top, right, bottom = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
    pad = 64
    img = Image.new(
        "L", (int(right - left) + pad * 2, int(bottom - top) + pad * 2), 255
    )
    ImageDraw.Draw(img).text((pad - left, pad - top), text, font=font, fill=0)
    return img


def _settings() -> Settings:
    return Settings(
        max_workers=1, tesseract_config=DEFAULT_TESSERACT_CONFIG, pdf_dpi=150
    )


def _make_text_pdf(text: str) -> bytes:
    """A minimal PDF carrying a real text layer, built without extra deps.

    Pillow can only produce image-only PDFs, which would exercise the OCR path
    again; this hand-rolled file has a genuine Helvetica text object so
    pdf_inspector classifies it `text_based`.
    """
    content = f"BT /F1 14 Tf 40 700 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def test_full_pipeline_image_ocr() -> None:
    buf = io.BytesIO()
    _make_image(EXPECTED).save(buf, format="PNG")

    content, method = extract(buf.getvalue(), _settings())

    assert method == "Image OCR"
    assert EXPECTED in content


def test_full_pipeline_scanned_pdf_ocr() -> None:
    buf = io.BytesIO()
    _make_image(EXPECTED).convert("RGB").save(buf, format="PDF")

    content, method = extract(buf.getvalue(), _settings())

    assert method == "PDF Inspector / OCR"
    assert EXPECTED in content


def test_full_pipeline_text_based_pdf_skips_ocr() -> None:
    """A real text-layer PDF must be read natively, with no OCR at all.

    Guards the pdf_inspector `text_based` shortcut end to end: the assertion on
    elapsed time is deliberately loose, but rasterising + OCRing this page
    takes far longer than the bound, so a regression that drops the native
    path fails here.
    """
    sentence = "The quick brown fox jumps over the lazy dog. " * 3
    data = _make_text_pdf(sentence)

    start = time.perf_counter()
    content, method = extract(data, _settings())
    elapsed = time.perf_counter() - start

    assert method == "PDF Inspector / OCR"
    assert "quick brown fox" in content
    assert elapsed < 1.0, f"native PDF path took {elapsed:.2f}s; OCR likely ran"


def test_full_pipeline_multipage_scanned_pdf_spans_batches() -> None:
    """OCR batching must not drop or reorder pages.

    Five pages with a batch size of four forces a second, partial batch.
    """
    words = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO"]
    pages = [_make_image(w).convert("RGB") for w in words]
    buf = io.BytesIO()
    pages[0].save(buf, format="PDF", save_all=True, append_images=pages[1:])

    content, method = extract(buf.getvalue(), _settings())

    assert method == "PDF Inspector / OCR"
    for word in words:
        assert word in content, f"page {word} missing from batched OCR output"
    positions = [content.index(w) for w in words]
    assert positions == sorted(positions), "batched OCR reordered pages"


def test_full_pipeline_legacy_xls_is_unsupported_not_a_crash() -> None:
    """Legacy OLE2 Office files degrade to empty content, never a 500.

    anydoc has no `xls` format, so routing these to it would raise and become
    an HTTP 500. This pins the deliberate `Unsupported filetype` outcome.
    """
    ole2 = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]) + b"\x00" * 504

    content, method = extract(ole2, _settings())

    assert method == "Unsupported filetype"
    assert content == ""


def test_full_pipeline_plain_text_native() -> None:
    """Real libmagic sniff of text/* takes the zero-OCR native path."""
    content, method = extract(b"just some plain text\n", _settings())

    assert method == "Native Text"
    assert "just some plain text" in content


def test_full_pipeline_healthy_csv() -> None:
    """A well-formed CSV goes through the real anydoc CSV parser."""
    content, method = extract(b"name,qty\nbolt,4\nnut,7\n", _settings())

    assert method == "Anydoc Native"
    assert "bolt" in content and "nut" in content


def test_full_pipeline_single_column_csv_is_plain_text() -> None:
    """Real libmagic: no delimiter means no `text/csv`, so no anydoc table."""
    content, method = extract(b"name\nbolt\nnut\n", _settings())

    assert method == "Native Text"
    assert "bolt" in content and "|" not in content


def test_full_pipeline_malformed_csv_is_never_lost() -> None:
    """Whatever the real anydoc does with broken quoting, content survives.

    anydoc is tolerant and may well parse this; the guarantee under test is
    that the request does not fail either way and the data is still ingested.
    """
    data = b'a,b,c\n1,2,3\n"oops,5,6\n'

    content, method = extract(data, _settings())

    assert method in ("Anydoc Native", "Native Text (CSV fallback)")
    assert content.strip(), "malformed CSV produced no content at all"
    assert "oops" in content
