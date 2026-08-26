"""Extension-based dispatch to the concrete extractors."""

import magic
import mimetypes
import anydoc
from ..config import Settings
from . import image, pdf


TESSERACT_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")
ANYDOC_EXTENSIONS = (".doc", ".docx", ".odt", ".pdf", ".ppt", ".pptx", ".rtf", ".epub", ".xlsx", ".ods", ".odp", ".csv")


def extract(data: bytes, settings: Settings) -> tuple[str, str]:
    """Extract text from `data` based on the `filename` extension.

    Returns a (content, method) tuple, where `method` is a short label
    used in the service logs.
    """
    md_extract = ""
    msg = "Unsupported filetype"

    mime_type = magic.from_buffer(data, mime=True)
    extension = mimetypes.guess_extension(mime_type)

    if extension in TESSERACT_IMAGE_EXTENSIONS:
        md_extract = image.extract(data, settings)
        msg = "Image OCR"
    elif extension == ".pdf":
        md_extract = pdf.extract(data, settings)
        msg = "PDF Inspector / OCR"
    elif extension == ".csv":
        md_extract = anydoc.to_markdown_bytes(data, "csv")
        msg = "Anydoc Native"
    elif extension in ANYDOC_EXTENSIONS:
        md_extract = anydoc.to_markdown_bytes(data)
        msg = "Anydoc Native"
    elif mime_type.startswith('text'):
        md_extract = data.decode("utf-8", errors="replace")
        msg = "Native Text"
    return md_extract, msg
