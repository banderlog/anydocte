"""Smart PDF handling: native extraction via pdf-inspector, OCR fallback."""

import logging
from typing import List, Optional

import pdf_inspector
from pdf2image import convert_from_bytes, pdfinfo_from_bytes
import pytesseract

from ..config import Settings

logger = logging.getLogger("extractor-proxy")

# Pages are rendered in batches instead of all at once: at the default 200 DPI
# an A4 page costs ~12 MB as RGB, so a few hundred pages rendered eagerly would
# exhaust RAM (and MAX_WORKERS multiplies it). Batching bounds peak memory to
# this many pages regardless of document length; output is unchanged.
OCR_PAGE_BATCH = 4


def _page_count(pdf_bytes: bytes) -> Optional[int]:
    """Page count without rendering; None if poppler cannot report it."""
    try:
        pages = pdfinfo_from_bytes(pdf_bytes).get("Pages")
        return int(pages) if pages is not None else None
    except Exception:
        return None


def _full_pdf_ocr(pdf_bytes: bytes, settings: Settings) -> str:
    total = _page_count(pdf_bytes)
    if total is not None:
        logger.info(f"OCR rendering {total} page(s) in batches of {OCR_PAGE_BATCH}")

    extracted_pages: List[str] = []
    first = 1
    while total is None or first <= total:
        last = first + OCR_PAGE_BATCH - 1
        if total is not None:
            last = min(last, total)
        pages = convert_from_bytes(
            pdf_bytes, fmt="png", dpi=settings.pdf_dpi, first_page=first, last_page=last
        )
        if not pages:
            break
        for page in pages:
            try:
                extracted_pages.append(
                    pytesseract.image_to_string(
                        page, config=settings.tesseract_config
                    ).strip()
                )
            finally:
                # Release each rendered bitmap as soon as it is consumed.
                page.close()
        first = last + 1

    return "\n\n".join(filter(None, extracted_pages))


def extract(pdf_bytes: bytes, settings: Settings) -> str:
    try:
        result = pdf_inspector.process_pdf_bytes(pdf_bytes)
        pdf_type = getattr(result, "pdf_type", "").lower()
        markdown = getattr(result, "markdown", None)
        pages_needing_ocr = getattr(result, "pages_needing_ocr", [])

        logger.info(
            f"PDF Inspector: type='{pdf_type}', confidence={getattr(result, 'confidence', 1.0):.2f}, "
            f"pages_needing_ocr={pages_needing_ocr}"
        )

        if pdf_type == "text_based" and markdown and len(markdown.strip()) > 20:
            logger.info("PDF Method: Native Markdown (pdf-inspector / Zero OCR)")
            # pdf_inspector is untyped, so `markdown` is Any; narrow it here.
            native: str = markdown.strip()
            return native

        if pdf_type == "mixed" and pages_needing_ocr:
            logger.info(
                f"PDF Method: Mixed detected (needs OCR on {pages_needing_ocr}). "
                f"Running OCR config: '{settings.tesseract_config}'..."
            )
            return _full_pdf_ocr(pdf_bytes, settings)

    except Exception as e:
        logger.warning(
            f"pdf-inspector failed to inspect PDF ({str(e)}). Cascading to standard OCR..."
        )

    logger.info(
        f"PDF Method: Scanned/Image PDF -> Running Tesseract OCR "
        f"config: '{settings.tesseract_config}' (DPI: {settings.pdf_dpi})"
    )
    return _full_pdf_ocr(pdf_bytes, settings)
