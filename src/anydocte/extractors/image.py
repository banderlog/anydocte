"""Tesseract OCR for standard image formats."""

import io

import pytesseract
from PIL import Image

from ..config import Settings


def extract(image_bytes: bytes, settings: Settings) -> str:
    with Image.open(io.BytesIO(image_bytes)) as img:
        return pytesseract.image_to_string(img, config=settings.tesseract_config)
