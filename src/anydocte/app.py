"""FastAPI application factory: HTTP ingestion and routing only."""

import asyncio
import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings
from .extractors import extract

logger = logging.getLogger("extractor-proxy")


def create_app(settings: Settings) -> FastAPI:
    executor = ThreadPoolExecutor(max_workers=settings.max_workers)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        executor.shutdown(wait=False)

    app = FastAPI(
        title="Open WebUI Universal Document Extraction Proxy",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.executor = executor

    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "max_workers": settings.max_workers,
            "tesseract_custom_config": settings.tesseract_config,
            "pdf_dpi": settings.pdf_dpi,
        }

    async def ingest(request: Request, filename: str) -> tuple[bytes, str]:
        file_bytes = await request.body()
        logger.info(
            f"Ingested via Raw Stream: '{filename}' [Size: {len(file_bytes)} bytes]"
        )
        return file_bytes, filename

    async def extract_content(
        request: Request,
        x_filename: Optional[str] = Header(None, alias="X-Filename"),
    ):
        filename = x_filename or "document.docx"
        file_bytes, filename = await ingest(request, filename)

        if not file_bytes:
            raise HTTPException(
                status_code=400, detail="Empty request payload received."
            )

        loop = asyncio.get_running_loop()
        try:
            content, method = await loop.run_in_executor(
                executor, lambda: extract(file_bytes, settings)
            )
            logger.info(f"SUCCESS: Extracted '{filename}' [Method: {method}]")
            return {"page_content": content.strip(), "metadata": {}}
        except Exception as e:
            logger.error(
                f"FAILURE: Processing error on '{filename}'. Details: {str(e)}"
            )
            return JSONResponse(
                status_code=500,
                content={"detail": f"Internal pipeline crash: {str(e)}"},
            )

    app.api_route("/process", methods=["POST", "PUT"])(extract_content)
    app.api_route("/", methods=["POST"])(extract_content)

    return app
