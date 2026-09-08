import os

import pytest

from anydocte.config import Settings, env_int


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


@pytest.mark.parametrize("bad", ["0", "-1"])
def test_non_positive_max_workers_is_rejected(monkeypatch, bad):
    """Caught at config time, not deep inside ThreadPoolExecutor."""
    monkeypatch.setenv("MAX_WORKERS", bad)
    with pytest.raises(ValueError, match="max_workers must be >= 1"):
        Settings.from_env()


@pytest.mark.parametrize("bad", ["0", "-50"])
def test_non_positive_pdf_dpi_is_rejected(monkeypatch, bad):
    monkeypatch.setenv("PDF_DPI", bad)
    monkeypatch.delenv("MAX_WORKERS", raising=False)
    with pytest.raises(ValueError, match="pdf_dpi must be >= 1"):
        Settings.from_env()


@pytest.mark.parametrize("var", ["MAX_WORKERS", "PDF_DPI"])
def test_non_numeric_env_names_the_offending_var(monkeypatch, var):
    """A bad value must be diagnosable, not a bare int() traceback."""
    monkeypatch.delenv("MAX_WORKERS", raising=False)
    monkeypatch.delenv("PDF_DPI", raising=False)
    monkeypatch.setenv(var, "not-a-number")
    with pytest.raises(ValueError, match=f"invalid {var}='not-a-number'"):
        Settings.from_env()


def test_env_int_returns_default_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_UNSET_VAR", raising=False)
    assert env_int("SOME_UNSET_VAR", 42) == 42


def test_valid_boundary_values_are_accepted(monkeypatch):
    monkeypatch.setenv("MAX_WORKERS", "1")
    monkeypatch.setenv("PDF_DPI", "1")
    s = Settings.from_env()
    assert (s.max_workers, s.pdf_dpi) == (1, 1)
