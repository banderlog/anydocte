# CONSTITUTION

Binding rules for every agent (AI or human) working in this repository.
Read this file before making any change. If a later instruction conflicts
with this file, the explicit instruction wins — but say so and, when the
conflict is permanent, update this file in the same change.

Precedence: explicit user instruction > this Constitution > habit.

## 1. Identity

AnyDocTE is a universal document-extraction proxy for Open WebUI. It accepts
raw document bytes over HTTP and returns extracted text content.

Pipeline by file type (dispatch lives in `src/anydocte/extractors/__init__.py`):

| Input | Path | Method label in logs |
|---|---|---|
| Image extensions (png/jpg/jpeg/tiff/bmp/webp) | Tesseract OCR | `Image OCR` |
| `.pdf` | pdf_inspector analysis; OCR fallback for scanned pages | `PDF Inspector / OCR` |
| Everything else | anydoc → markdown | `Anydoc Native` |

The project version is declared in **one** place: `pyproject.toml`
(`[project] version`), mirrored in `src/anydocte/__init__.py`
(`__version__`). Keep the two in sync.

## 2. Hard rules

Non-negotiable without an explicit user decision:

1. **Raw streams only.** The API accepts the request body as raw bytes.
   Multipart/form-data parsing was deliberately removed; do not re-add it,
   and do not re-declare `python-multipart` as a dependency.
2. **Exact wire contract.** Response shapes, HTTP codes, and message strings
   in §3 are byte-stable — downstream code parses them.
3. **Log wording is stable.** The logger is named `extractor-proxy` and the
   message templates (e.g. `Ingested via Raw Stream: '...'`,
   `SUCCESS: Extracted '...' [Method: ...]`,
   `FAILURE: Processing error on '...'. Details: ...`) may be reworded only
   with user approval.
4. **No new runtime dependencies** without user approval. Dev-only additions
   (pytest / mypy plugins, etc.) are fine.
5. **Two test tiers.** Unit/API tests must not require the OCR stack —
   they monkeypatch the extractors. Full-pipeline tests must use the real
   OCR stack (Tesseract + poppler are guaranteed present, see §6).
6. **Configuration is declarative.** Data flows CLI args → `Settings`
   (frozen dataclass, env read once via `Settings.from_env()`) →
   `create_app(settings)`. No module-level config globals, no env re-reads
   at request time.
7. **Transport stays in `app.py`, logic stays in `extractors/`.**
   `app.py` imports the dispatch function only; `cli.py` contains no
   business logic.
8. **Verification is not optional.** Run the full protocol in §5 before
   declaring anything done, and report the results.
9. **Git discipline.** See §7 — no commits unless asked, ever.
10. **No secrets.** Never stage or commit credentials, API keys, tokens,
    auth files (e.g. `auth.json`), `.env` files, or private-key material.
    If a file might contain secrets, stop and ask the owner before
    staging it.

## 3. Behavior contract

### Endpoints

| Route | Methods | Purpose |
|---|---|---|
| `/health` | GET | Liveness + runtime config echo |
| `/process` | POST, PUT | Extraction |
| `/` | POST | Alias of `/process` |

- The input filename comes from the `X-Filename` header; default
  `document.docx`.
- Body may be empty; everything is bytes.

### Responses

| Case | Status | Body (exact) |
|---|---|---|
| Success | 200 | `{"page_content": "<content, .strip() applied>", "metadata": {}}` |
| Empty body | 400 | `{"detail": "Empty request payload received."}` |
| Any exception in the extraction pipeline | 500 | `{"detail": "Internal pipeline crash: <str(e)>"}` |

`GET /health` returns exactly:

```json
{"status": "healthy", "max_workers": N, "tesseract_custom_config": "<str>", "pdf_dpi": N}
```

### Configuration

Environment variables are read **once** at startup; CLI flags override env.

| Env var | Flag | Default |
|---|---|---|
| `HOST` | `--host` | `0.0.0.0` |
| `PORT` | `--port` | `5005` |
| `MAX_WORKERS` | `--max-workers` | CPU count (fallback 4) |
| `TESSERACT_CUSTOM_CONFIG` | `--tesseract-config` | `-l eng+ukr+rus --oem 1 --psm 3` |
| `PDF_DPI` | `--pdf-dpi` | `200` |

## 4. Architecture map

```
src/anydocte/
├── __init__.py      # __version__ (must match pyproject.toml)
├── __main__.py      # python -m anydocte
├── cli.py           # argparse → Settings → uvicorn
├── config.py        # frozen Settings dataclass + Settings.from_env()
├── app.py           # create_app(settings): HTTP ingestion + routing only
└── extractors/
    ├── __init__.py  # dispatch by extension → (content, method_label)
    ├── image.py     # tesseract image OCR
    ├── pdf.py       # pdf_inspector smart routing + full-page OCR fallback
    └── office.py    # anydoc → markdown
tests/               # pytest: unit (monkeypatched) + full-pipeline (real OCR)
docker.nix           # image: eng+ukr+rus tessdata (slim)
docker_all.nix       # image: all tesseract languages
```

Rules:

- A new file family = a new module under `src/anydocte/extractors/` + one
  dispatch branch in its `__init__.py` + at least one test in `tests/`.
- `app.py` never imports a concrete extractor; dispatch is opaque to it.
- No transport code in `extractors/`, no extraction logic in `app.py`/`cli.py`.

## 5. Verification protocol

Run ALL of the following before declaring a change done, and report results:

```bash
/workspace/.venv/bin/pytest -q      # expect 18/18 passed (16 unit + 2 full-pipeline)
/workspace/.venv/bin/mypy           # expect: no issues found
/workspace/.venv/bin/anydocte --help
/workspace/.venv/bin/python -m anydocte --help
# Nix syntax check (this VM's /nix/store is read-only, use a scratch store):
nix-instantiate --store /tmp/opencode/nixstore --parse docker.nix docker_all.nix
```

Full-pipeline smoke (real OCR; the stack is guaranteed in §6):

```bash
/workspace/.venv/bin/anydocte --port 5005 &
curl -s localhost:5005/health
curl -s -X POST localhost:5005/process -H 'X-Filename: a.png' --data-binary @a.png
curl -s -X POST localhost:5005/process -H 'X-Filename: a.pdf' --data-binary @a.pdf
```

## 6. Environment facts

- This repo lives in a **nixcage VM**. A VM reboot wipes everything
  **except `/workspace`**. Anything that must survive goes under
  `/workspace`.
- Python: use the project venv at `/workspace/.venv`
  (`/workspace/.venv/bin/pip install -e '.[dev]'` after dependency changes).
  There is no `python` on PATH; the interpreter lives in the nix store.
- `/nix/store` is **read-only** here. Any nix command that needs to write
  must use a scratch store, e.g. `--store /tmp/opencode/nixstore`.
  Flakes that fetch nixpkgs cannot be evaluated in this VM.
- Tesseract 5.5.3 (full language set) and `poppler-utils` are installed in
  the VM system packages; they power the full-pipeline tests (§5).
- **Git: the agent has no credentials.** Commits may be created locally when
  explicitly asked; **pushing is always done manually by the owner.**
- `experiments/` is deliberately untracked on the main branch. It holds
  long-term work toward a pure-flake packaging of this repo; never wire it
  into builds, tests, or dependencies.
- The agent's own session state is persisted at `/workspace/.opencode`
  (symlinked into the home directory by a boot systemd unit). Do not move
  or rename it.

## 7. Definitions

- **Done** = code and tests updated + every §5 check passing + results
  reported to the user.
- **External interface** = anything in §3 (endpoints, shapes, strings,
  env vars, flags). Changes to it require an explicit user decision.
