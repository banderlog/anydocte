import anydocte.extractors as extractors
from anydocte.config import Settings
from anydocte.extractors import image, office, pdf

SETTINGS = Settings(max_workers=1, tesseract_config="-l eng", pdf_dpi=150)


def test_image_extensions(monkeypatch):
    monkeypatch.setattr(image, "extract", lambda data, s: "<img>")
    for name in ("a.png", "b.JPG", "c.jpeg", "d.tiff", "e.bmp", "f.WEBP"):
        assert extractors.extract(name, b"x", SETTINGS) == ("<img>", "Image OCR")


def test_pdf(monkeypatch):
    monkeypatch.setattr(pdf, "extract", lambda data, s: "<pdf>")
    assert extractors.extract("scan.pdf", b"x", SETTINGS) == (
        "<pdf>",
        "PDF Inspector / OCR",
    )


def test_office_fallback(monkeypatch):
    monkeypatch.setattr(office, "extract", lambda data, s: "<office>")
    for name in ("doc.docx", "data.xlsx", "slides.PPTX", "book.epub", "no_ext"):
        assert extractors.extract(name, b"x", SETTINGS) == ("<office>", "Anydoc Native")


def test_settings_passed_through(monkeypatch):
    captured = {}

    def fake(data, s):
        captured["s"] = s
        return "ok"

    monkeypatch.setattr(image, "extract", fake)
    assert extractors.extract("a.png", b"x", SETTINGS) == ("ok", "Image OCR")
    assert captured["s"] is SETTINGS
