"""Content-based dispatch to the concrete extractors.

The file type is sniffed from the bytes themselves with libmagic, so the
client-supplied filename never influences routing.
"""

import logging
import mimetypes

import anydoc
import magic

from ..config import Settings
from . import image, pdf

logger = logging.getLogger("extractor-proxy")

TESSERACT_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")
ANYDOC_EXTENSIONS = (
    ".doc",
    ".docx",
    ".odt",
    ".ppt",
    ".pptx",
    ".rtf",
    ".epub",
    ".xlsx",
    ".ods",
    ".odp",
)


def _decode_text(data: bytes) -> str:
    """Best-effort UTF-8 decode; undecodable bytes are replaced, never raised."""
    return data.decode("utf-8", errors="replace")


def extract(data: bytes, settings: Settings) -> tuple[str, str]:
    """Extract text from `data`, routing on its sniffed MIME type.

    Returns a (content, method) tuple, where `method` is a short label
    used in the service logs.
    """
    mime_type = magic.from_buffer(data, mime=True)
    extension = mimetypes.guess_extension(mime_type)

    if extension in TESSERACT_IMAGE_EXTENSIONS:
        return image.extract(data, settings), "Image OCR"

    if extension == ".pdf":
        return pdf.extract(data, settings), "PDF Inspector / OCR"

    # anydoc cannot sniff a bare CSV, so the format is passed explicitly.
    # A malformed CSV (ragged rows, broken quoting) must still be ingested,
    # so fall back to plain text rather than failing the whole request.
    if extension == ".csv":
        try:
            return anydoc.to_markdown_bytes(data, "csv"), "Anydoc Native"
        except Exception as e:
            logger.warning(
                f"anydoc failed to parse CSV ({str(e)}). "
                f"Falling back to plain text..."
            )
            return _decode_text(data), "Native Text (CSV fallback)"

    if extension in ANYDOC_EXTENSIONS:
        return anydoc.to_markdown_bytes(data), "Anydoc Native"

    if mime_type.startswith("text"):
        return _decode_text(data), "Native Text"

    return "", "Unsupported filetype"
