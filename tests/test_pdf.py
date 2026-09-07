"""Unit tests for the PDF branch logic (CONSTITUTION.md rule 5: no real OCR).

`pdf_inspector.process_pdf_bytes` and the OCR renderer are both stubbed, so
these exercise the routing decisions in `pdf.extract` — the native
`text_based` shortcut, the `mixed` OCR path and the inspector-failure cascade —
without touching tesseract or poppler.
"""

from typing import Any, List, Optional

import pytest

import pdf_inspector

from anydocte.config import Settings
from anydocte.extractors import pdf

SETTINGS = Settings(max_workers=1, tesseract_config="-l eng", pdf_dpi=150)


class FakeResult:
    """Stand-in for pdf_inspector's result; pdf.extract reads it via getattr."""

    def __init__(
        self,
        pdf_type: str = "scanned",
        markdown: Optional[str] = None,
        pages_needing_ocr: Optional[List[int]] = None,
        confidence: float = 0.9,
    ) -> None:
        self.pdf_type = pdf_type
        self.markdown = markdown
        self.pages_needing_ocr = pages_needing_ocr if pages_needing_ocr else []
        self.confidence = confidence


@pytest.fixture()
def no_ocr(monkeypatch: pytest.MonkeyPatch) -> List[bool]:
    """Replace the OCR renderer; records whether it ran."""
    ran: List[bool] = []

    def fake_ocr(data: bytes, settings: Settings) -> str:
        ran.append(True)
        return "<ocr>"

    monkeypatch.setattr(pdf, "_full_pdf_ocr", fake_ocr)
    return ran


def _stub_inspector(monkeypatch: pytest.MonkeyPatch, result: Any) -> None:
    monkeypatch.setattr(
        pdf_inspector, "process_pdf_bytes", lambda data: result
    )


def test_text_based_returns_native_markdown_without_ocr(
    monkeypatch: pytest.MonkeyPatch, no_ocr: List[bool]
) -> None:
    """The zero-OCR fast path: real text PDFs must not be rasterised."""
    body = "This is a genuine text layer, comfortably over twenty characters."
    _stub_inspector(monkeypatch, FakeResult(pdf_type="text_based", markdown=body))

    assert pdf.extract(b"%PDF-1.4", SETTINGS) == body
    assert not no_ocr, "OCR ran on a text-based PDF"


def test_text_based_with_too_little_text_falls_back_to_ocr(
    monkeypatch: pytest.MonkeyPatch, no_ocr: List[bool]
) -> None:
    """A near-empty text layer is treated as unreliable, so OCR still runs."""
    _stub_inspector(monkeypatch, FakeResult(pdf_type="text_based", markdown="short"))

    assert pdf.extract(b"%PDF-1.4", SETTINGS) == "<ocr>"
    assert no_ocr


def test_text_based_without_markdown_falls_back_to_ocr(
    monkeypatch: pytest.MonkeyPatch, no_ocr: List[bool]
) -> None:
    _stub_inspector(monkeypatch, FakeResult(pdf_type="text_based", markdown=None))

    assert pdf.extract(b"%PDF-1.4", SETTINGS) == "<ocr>"
    assert no_ocr


def test_mixed_with_pages_needing_ocr_runs_ocr(
    monkeypatch: pytest.MonkeyPatch, no_ocr: List[bool]
) -> None:
    _stub_inspector(
        monkeypatch, FakeResult(pdf_type="mixed", pages_needing_ocr=[2, 5])
    )

    assert pdf.extract(b"%PDF-1.4", SETTINGS) == "<ocr>"
    assert no_ocr


def test_scanned_runs_ocr(
    monkeypatch: pytest.MonkeyPatch, no_ocr: List[bool]
) -> None:
    _stub_inspector(monkeypatch, FakeResult(pdf_type="scanned"))

    assert pdf.extract(b"%PDF-1.4", SETTINGS) == "<ocr>"
    assert no_ocr


def test_inspector_failure_cascades_to_ocr(
    monkeypatch: pytest.MonkeyPatch, no_ocr: List[bool], caplog: pytest.LogCaptureFixture
) -> None:
    """A broken inspector must degrade to OCR, not fail the request."""

    def boom(data: bytes) -> Any:
        raise RuntimeError("inspector exploded")

    monkeypatch.setattr(pdf_inspector, "process_pdf_bytes", boom)

    with caplog.at_level("WARNING", logger="extractor-proxy"):
        assert pdf.extract(b"%PDF-1.4", SETTINGS) == "<ocr>"

    assert no_ocr
    assert "inspector exploded" in caplog.text


def test_ocr_failure_still_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only CSV degrades; a failing OCR pass must surface as a 500 upstream."""
    _stub_inspector(monkeypatch, FakeResult(pdf_type="scanned"))

    def boom(data: bytes, settings: Settings) -> str:
        raise RuntimeError("tesseract died")

    monkeypatch.setattr(pdf, "_full_pdf_ocr", boom)

    with pytest.raises(RuntimeError, match="tesseract died"):
        pdf.extract(b"%PDF-1.4", SETTINGS)
