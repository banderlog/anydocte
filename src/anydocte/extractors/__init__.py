"""Extension-based dispatch to the concrete extractors."""

from ..config import Settings
from . import image, office, pdf

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp")


def extract(filename: str, data: bytes, settings: Settings) -> tuple[str, str]:
    """Extract text from `data` based on the `filename` extension.

    Returns a (content, method) tuple, where `method` is a short label
    used in the service logs.
    """
    name = filename.lower()
    if name.endswith(IMAGE_EXTENSIONS):
        return image.extract(data, settings), "Image OCR"
    if name.endswith(".pdf"):
        return pdf.extract(data, settings), "PDF Inspector / OCR"
    return office.extract(data, settings), "Anydoc Native"
