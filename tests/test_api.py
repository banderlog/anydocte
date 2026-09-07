import time

import pytest
from fastapi.testclient import TestClient

import anydocte.app as app_module
from anydocte.app import create_app
from anydocte.config import Settings


@pytest.fixture()
def settings():
    return Settings(max_workers=1, tesseract_config="-l eng", pdf_dpi=150)


@pytest.fixture()
def app(settings, monkeypatch):
    monkeypatch.setattr(
        app_module, "extract", lambda data, s: (data.decode(), "Fake Method")
    )
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


def test_health(client, settings):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {
        "status": "healthy",
        "max_workers": settings.max_workers,
        "tesseract_custom_config": settings.tesseract_config,
        "pdf_dpi": settings.pdf_dpi,
    }


def test_process_raw_stream(client):
    r = client.post("/process", content=b"hello", headers={"X-Filename": "a.txt"})
    assert r.status_code == 200
    assert r.json() == {"page_content": "hello", "metadata": {}}


def test_process_put_route(client):
    r = client.put("/process", content=b"hi", headers={"X-Filename": "a.txt"})
    assert r.status_code == 200
    assert r.json() == {"page_content": "hi", "metadata": {}}


def test_root_post_route(client):
    r = client.post("/", content=b"hi", headers={"X-Filename": "a.txt"})
    assert r.status_code == 200
    assert r.json() == {"page_content": "hi", "metadata": {}}


def test_process_empty_payload_returns_400(client):
    r = client.post("/process", content=b"")
    assert r.status_code == 400
    assert r.json() == {"detail": "Empty request payload received."}


def test_process_failure_returns_500(app, monkeypatch):
    def boom(data, s):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(app_module, "extract", boom)
    with TestClient(app) as c:
        r = c.post("/process", content=b"x", headers={"X-Filename": "a.txt"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal pipeline crash: kaboom"}


def test_process_without_filename_header_uses_default(app, caplog):
    """X-Filename is optional; §3 documents `document.docx` as the default."""
    with caplog.at_level("INFO", logger="extractor-proxy"):
        with TestClient(app) as c:
            r = c.post("/process", content=b"hi")

    assert r.status_code == 200
    assert r.json() == {"page_content": "hi", "metadata": {}}
    assert "document.docx" in caplog.text


def test_extraction_completes_across_shutdown(settings, monkeypatch):
    """The executor drains on shutdown instead of killing in-flight work."""
    finished = []

    def slow(data, s):
        time.sleep(0.3)
        finished.append(True)
        return "done", "Slow Method"

    monkeypatch.setattr(app_module, "extract", slow)
    app = create_app(settings)

    with TestClient(app) as c:
        r = c.post("/process", content=b"x", headers={"X-Filename": "a.txt"})

    assert r.status_code == 200
    assert r.json() == {"page_content": "done", "metadata": {}}
    assert finished, "extraction was killed instead of draining"
