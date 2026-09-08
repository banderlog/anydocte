"""Command line entrypoint: argparse -> Settings -> uvicorn."""

import argparse
import logging
import os
import sys

import uvicorn

from .app import create_app
from .config import Settings, env_int

logger = logging.getLogger("extractor-proxy")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def build_arg_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Universal Document Extraction Proxy")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host address to bind to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=env_int("PORT", 5005),
        help="Port to bind to",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=settings.max_workers,
        help="Number of worker threads (default: from MAX_WORKERS or CPU count)",
    )
    parser.add_argument(
        "--tesseract-config",
        type=str,
        default=settings.tesseract_config,
        help="Custom Tesseract config flags (e.g. '-l rus+eng+ukr --oem 1 --psm 3')",
    )
    parser.add_argument(
        "--pdf-dpi",
        type=int,
        default=settings.pdf_dpi,
        help="DPI resolution for rendering PDF pages to images (default: 200)",
    )
    return parser


def settings_from_args(args: argparse.Namespace) -> Settings:
    return Settings(
        max_workers=args.max_workers,
        tesseract_config=args.tesseract_config,
        pdf_dpi=args.pdf_dpi,
    )


def main() -> None:
    configure_logging()
    # Misconfiguration is a user error: report it on one line and exit 2
    # (argparse's own convention) instead of dumping a traceback.
    try:
        args = build_arg_parser(Settings.from_env()).parse_args()
        settings = settings_from_args(args)
    except ValueError as e:
        raise SystemExit(f"anydocte: {e}") from None

    app = create_app(settings)
    logger.info(
        f"Starting extraction proxy on {args.host}:{args.port} | "
        f"Workers: {settings.max_workers} | "
        f"OCR Config: '{settings.tesseract_config}' | PDF DPI: {settings.pdf_dpi}"
    )
    uvicorn.run(app, host=args.host, port=args.port, reload=False)
