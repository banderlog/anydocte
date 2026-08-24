import os

from anydocte.config import Settings


def test_env_defaults(monkeypatch):
    monkeypatch.delenv("MAX_WORKERS", raising=False)
    monkeypatch.delenv("TESSERACT_CUSTOM_CONFIG", raising=False)
    monkeypatch.delenv("PDF_DPI", raising=False)
    s = Settings.from_env()
    assert s.max_workers == (os.cpu_count() or 4)
    assert s.tesseract_config == "-l eng+ukr+rus --oem 1 --psm 3"
    assert s.pdf_dpi == 200


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("MAX_WORKERS", "8")
    monkeypatch.setenv("TESSERACT_CUSTOM_CONFIG", "-l eng --psm 6")
    monkeypatch.setenv("PDF_DPI", "300")
    s = Settings.from_env()
    assert (s.max_workers, s.tesseract_config, s.pdf_dpi) == (8, "-l eng --psm 6", 300)
