"""Immutable runtime settings, read once from environment variables."""

import os
from dataclasses import dataclass

DEFAULT_TESSERACT_CONFIG = "-l eng+ukr+rus --oem 1 --psm 3"
DEFAULT_PDF_DPI = 200


def env_int(name: str, default: int) -> int:
    """Read an integer env var, reporting a bad value by its name.

    A malformed value is a configuration mistake, not a crash: raising
    ValueError here means the offending variable is named in the message
    instead of surfacing as a bare `int()` traceback.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"invalid {name}={raw!r}: expected an integer") from None


@dataclass(frozen=True)
class Settings:
    max_workers: int
    tesseract_config: str
    pdf_dpi: int

    def __post_init__(self) -> None:
        # Caught here rather than deep inside ThreadPoolExecutor / the PDF
        # renderer, so the failure names the setting that is wrong.
        if self.max_workers < 1:
            raise ValueError(f"max_workers must be >= 1, got {self.max_workers}")
        if self.pdf_dpi < 1:
            raise ValueError(f"pdf_dpi must be >= 1, got {self.pdf_dpi}")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            max_workers=env_int("MAX_WORKERS", os.cpu_count() or 4),
            tesseract_config=os.getenv(
                "TESSERACT_CUSTOM_CONFIG", DEFAULT_TESSERACT_CONFIG
            ),
            pdf_dpi=env_int("PDF_DPI", DEFAULT_PDF_DPI),
        )
