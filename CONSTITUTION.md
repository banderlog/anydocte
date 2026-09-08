# CONSTITUTION

Binding rules for every agent (AI or human) working in this repository.
Read this file before making any change. If a later instruction conflicts
with this file, the explicit instruction wins — but say so and, when the
conflict is permanent, update this file in the same change.

Precedence: explicit user instruction > this Constitution > habit.

## 1. Identity

AnyDocTE is a universal document-extraction proxy for Open WebUI. It accepts
raw document bytes over HTTP and returns extracted text content.

Pipeline by file type (dispatch lives in `src/anydocte/extractors/__init__.py`).
Routing is **content-based**: the MIME type is sniffed from the bytes with
libmagic and mapped to an extension via `mimetypes.guess_extension`. The
client-supplied `X-Filename` is used for logging only and never influences
routing.

| Sniffed type | Path | Method label in logs |
|---|---|---|
| Images (png/jpg/jpeg/tiff/bmp/webp) | Tesseract OCR | `Image OCR` |
| `application/pdf` | pdf_inspector analysis; OCR fallback for scanned pages | `PDF Inspector / OCR` |
| `text/csv` | anydoc → markdown (format passed explicitly) | `Anydoc Native` |
| `text/csv` that anydoc cannot parse | UTF-8 decode, never a 500 | `Native Text (CSV fallback)` |
| Office/OpenDocument/rtf/epub | anydoc → markdown | `Anydoc Native` |
| Any other `text/*` | UTF-8 decode (`errors="replace"`) | `Native Text` |
| Anything else | no extraction; empty content | `Unsupported filetype` |

**A single-column CSV is not sniffed as CSV.** libmagic only reports
`text/csv` when it sees a delimiter, so `name\nbolt\nnut\n` comes back as
`text/plain` and takes the `Native Text` path instead of anydoc. Harmless —
the content is returned verbatim, just not as a markdown table — but it means
the `text/csv` row above depends on the data, not only the file's purpose.
A test pins this so the behaviour is not mistaken for a regression.

**Legacy `.xls` is deliberately unsupported.** anydoc's format list is
`csv, doc, docx, epub, odp, ods, odt, pdf, ppt, pptx, rtf, xlsx` — there is no
`xls`, and autodetect on OLE2 bytes raises. Adding `.xls` to
`ANYDOC_EXTENSIONS` would therefore convert today's clean `200` + empty content
into a `500` for every such upload. It stays in the `Unsupported filetype` row
until anydoc grows real support; a test pins this. Note `.doc`/`.ppt` *are*
anydoc formats and do route to it.

The project version is declared in **one** place:
`pyproject.toml`. `src/anydocte/__init__.py` (`__version__`) derives it via
`importlib.metadata.version("anydocte")`, and both nix images parse the same file.
Never hardcode it a second time.

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
   at request time. `Settings` validates its own fields in `__post_init__`,
   so an invalid value fails at startup with a message naming the setting.
   **Documented exception:** `HOST` and `PORT` are *not* `Settings` fields.
   They are bind-time transport arguments handed straight to `uvicorn.run()`
   and never reach `create_app`, so they stay in the argparse defaults;
   `Settings` carries extraction config only. This is deliberate — do not
   "fix" it by adding them, and note `/health` echoes `Settings`, so new
   fields there would change the response shape frozen in §3.
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
├── config.py        # frozen Settings (validated in __post_init__) +
│                    # Settings.from_env() + env_int()
├── app.py           # create_app(settings): HTTP ingestion + routing only
└── extractors/
    ├── __init__.py  # libmagic MIME dispatch → (content, method_label);
    │                # anydoc + native-text paths are inlined here
    ├── image.py     # tesseract image OCR
    └── pdf.py       # pdf_inspector smart routing + batched OCR fallback
tests/               # pytest: unit (monkeypatched) + full-pipeline (real OCR)
    ├── test_pdf.py  # pdf branch logic, inspector stubbed (no OCR)
    └── ...          # test_api / test_cli / test_config / test_dispatch /
                     # test_pipeline (the only real-OCR tier)
docker_slim.nix      # image: eng+ukr+rus tessdata
docker_full.nix      # image: all tesseract languages
nixcage.vm.nix       # dev VM: system packages + LD_LIBRARY_PATH for libmagic
```

Rules:

- A new file family = a new module under `src/anydocte/extractors/` + one
  dispatch branch in its `__init__.py` + at least one test in `tests/`.
  Dispatch branches key off the sniffed MIME type, never off `X-Filename`.
- **Corrupt CSV degrades, never fails.** A CSV that anydoc cannot parse is
  ingested as plain text (`Native Text (CSV fallback)`) with a `WARNING`,
  because a partially-readable file beats a lost one. This tolerance is
  deliberately scoped to CSV only — every other extractor still propagates
  its exception to the 500 handler in §3.
- `app.py` never imports a concrete extractor; dispatch is opaque to it.
- No transport code in `extractors/`, no extraction logic in `app.py`/`cli.py`.
- **PDF pages are OCR'd in batches, never all at once.** At the default 200 DPI
  an A4 page costs ~12 MB as RGB, so rendering a few hundred pages eagerly
  exhausts RAM (and `MAX_WORKERS` multiplies it). `pdf.py` renders
  `OCR_PAGE_BATCH` pages at a time via `first_page`/`last_page` and closes each
  bitmap after use; output is byte-identical to rendering everything at once.
  Batch size is a module constant on purpose — making it a `Settings` field
  would change the `/health` shape frozen in §3.
- **Invalid configuration fails at startup with a named error.** `Settings`
  validates its own fields (`__post_init__`), `env_int()` reports the offending
  variable, and `cli.main()` turns both into a one-line message + non-zero
  exit rather than a traceback.

## 5. Verification protocol

Run ALL of the following before declaring a change done, and report results:

```bash
/workspace/.venv/bin/pytest -q      # expect 75/75 passed (66 unit + 9 full-pipeline)
/workspace/.venv/bin/mypy           # expect: no issues found
                                    # (src/anydocte is checked strictly via a
                                    #  per-module override; tests stay lenient)
/workspace/.venv/bin/anydocte --help
/workspace/.venv/bin/python -m anydocte --help
# Nix syntax check (this VM's /nix/store is read-only, use a scratch store):
nix-instantiate --store /tmp/opencode/nixstore --parse \
  docker_slim.nix docker_full.nix nixcage.vm.nix
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
- `python-magic` is a ctypes wrapper that `dlopen()`s **native libmagic** at
  import time, so `LD_LIBRARY_PATH` must point at it or every import of
  `anydocte.extractors` fails. It is set declaratively via
  `pkgs.lib.makeLibraryPath` in three places, whose contents are *not*
  identical: `nixcage.vm.nix` (`environment.variables`, for the bare venv)
  needs only `[ pkgs.file ]`, while the `libPath` in `docker_slim.nix` /
  `docker_full.nix` also carries `pkgs.zlib`, because `libmagic.so.1` links
  `libz.so.1` and an image has no system zlib to fall back on. Only
  `pkgs.file` is required for libmagic itself; keep it in the package list of
  any environment that runs this code. Before adding anything else to a
  `libPath`, check with `ldd` that something in the stack (libmagic,
  tesseract, poppler, Pillow) actually links it.
  After editing `nixcage.vm.nix`, run `nixcage sync` and reboot the VM for
  the change to land.
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
