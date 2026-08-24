"""Office document handling (DOCX, XLSX, PPTX, EPUB, ...) via anydoc."""

import anydoc

from ..config import Settings


def extract(file_bytes: bytes, settings: Settings) -> str:
    output = anydoc.to_markdown_bytes(file_bytes)
    return (output or "").strip()
