import os

import anydocte.cli as cli
from anydocte.config import Settings


def test_defaults_come_from_env(monkeypatch):
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "6000")
    monkeypatch.setenv("MAX_WORKERS", "7")
    monkeypatch.setenv("TESSERACT_CUSTOM_CONFIG", "-l ukr")
    monkeypatch.setenv("PDF_DPI", "250")
    args = cli.build_arg_parser(Settings.from_env()).parse_args([])
    assert (args.host, args.port) == ("127.0.0.1", 6000)
    assert cli.settings_from_args(args) == Settings(
        max_workers=7, tesseract_config="-l ukr", pdf_dpi=250
    )


def test_bare_defaults(monkeypatch):
    for var in ("HOST", "PORT", "MAX_WORKERS", "TESSERACT_CUSTOM_CONFIG", "PDF_DPI"):
        monkeypatch.delenv(var, raising=False)
    args = cli.build_arg_parser(Settings.from_env()).parse_args([])
    assert (args.host, args.port) == ("0.0.0.0", 5005)
    assert (
        cli.settings_from_args(args)
        == Settings(
            max_workers=os.cpu_count() or 4,
            tesseract_config="-l eng+ukr+rus --oem 1 --psm 3",
            pdf_dpi=200,
        )
    )


def test_cli_overrides_env(monkeypatch):
    monkeypatch.setenv("MAX_WORKERS", "7")
    monkeypatch.setenv("TESSERACT_CUSTOM_CONFIG", "-l ukr")
    monkeypatch.setenv("PDF_DPI", "250")
    parser = cli.build_arg_parser(Settings.from_env())
    args = parser.parse_args(
        ["--max-workers", "2", "--tesseract-config", "-l eng", "--pdf-dpi", "100"]
    )
    assert cli.settings_from_args(args) == Settings(
        max_workers=2, tesseract_config="-l eng", pdf_dpi=100
    )


def test_main_wiring(monkeypatch):
    calls = {}

    def fake_uvicorn_run(app, **kwargs):
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(cli.uvicorn, "run", fake_uvicorn_run)
    monkeypatch.setenv("MAX_WORKERS", "3")
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setattr("sys.argv", ["anydocte", "--port", "7777"])

    cli.main()

    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 7777
    assert calls["reload"] is False
    assert calls["app"].state.settings.max_workers == 3
