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
        app_module, "extract", lambda filename, data, s: (data.decode(), "Fake Method")
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
    def boom(filename, data, s):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(app_module, "extract", boom)
    with TestClient(app) as c:
        r = c.post("/process", content=b"x", headers={"X-Filename": "a.txt"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal pipeline crash: kaboom"}
