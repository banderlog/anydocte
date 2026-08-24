"""Immutable runtime settings, read once from environment variables."""

import os
from dataclasses import dataclass

DEFAULT_TESSERACT_CONFIG = "-l eng+ukr+rus --oem 1 --psm 3"
DEFAULT_PDF_DPI = 200


@dataclass(frozen=True)
class Settings:
    max_workers: int
    tesseract_config: str
    pdf_dpi: int

    @classmethod
    def from_env(cls) -> "Settings":
        max_workers_env = os.getenv("MAX_WORKERS")
        return cls(
            max_workers=(
                int(max_workers_env)
                if max_workers_env is not None
                else (os.cpu_count() or 4)
            ),
            tesseract_config=os.getenv("TESSERACT_CUSTOM_CONFIG", DEFAULT_TESSERACT_CONFIG),
            pdf_dpi=int(os.getenv("PDF_DPI", str(DEFAULT_PDF_DPI))),
        )
