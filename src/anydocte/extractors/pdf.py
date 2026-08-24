"""Smart PDF handling: native extraction via pdf-inspector, OCR fallback."""

import logging

import pdf_inspector
from pdf2image import convert_from_bytes
import pytesseract

from ..config import Settings

logger = logging.getLogger("extractor-proxy")


def _full_pdf_ocr(pdf_bytes: bytes, settings: Settings) -> str:
    pages = convert_from_bytes(pdf_bytes, fmt="png", dpi=settings.pdf_dpi)
    extracted_pages = [
        pytesseract.image_to_string(page, config=settings.tesseract_config).strip()
        for page in pages
    ]
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
            return markdown.strip()

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
