"""Full-pipeline tests against the real OCR stack (CONSTITUTION.md, rule 5)."""

import io

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
