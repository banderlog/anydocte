# Anydocte

This repo provides an external document extraction service for integration of anydoc with openwebui.

Anydoc can't do OCR, so pdf_inspector is used to check if PDF needs OCR, than tesseract runs if needed.


## Dependencies

- System:
    - tesseract-ocr
    - poppler-utils
- Python:
    - `pyproject.toml` (install with `pip install -e .` or `uv pip install -e .`)


## Notes on tesseract

Tesseract languages are heavy, thus I have few versions:
- `docker_slim.nix` with rus+ukr+eng languages
- `docker_full.nix` with all languages
- bare python setup, so one can manage tesseract by himself

---

## Usage

### 1. Run server

#### 1.1 Bare python way

It implies that tesseract and poppler-utils already installed

```bash
# install the package with dependencies in a venv
python -m venv venv
./venv/bin/pip install -e .

# start with args
./venv/bin/anydocte --tesseract-config "-l eng+rus+ukr --psm 3" --max-workers 8 --port 5005
# (equivalent: ./venv/bin/python -m anydocte ...)

# OR start with envs
MAX_WORKERS=8 \
PORT=5005 \
PDF_DPI=300 \
TESSERACT_CUSTOM_CONFIG='-l eng --psm 6' \
./venv/bin/anydocte
```

#### 1.2 Docker way

##### 1.2.1 Quick start

```bash
# it will pull "full" image with all languages
docker run --rm -p 5005:5005 banderlog013/anydocte:latest
```

##### 1.2.2 Build from scratch

```bash
# build image
nix-build docker_full.nix

# load image
docker load < result

# start container
docker run --rm -p 5005:5005 \
  -e PDF_DPI=300 \
  anydocte:0.1.0-full
```


### 2. Set settings in openwebui

1. Admin -> Settings -> Documents -> Select "External"
2. Fill "Document Loader URL"
3. Fill some random symbols in "API key"

---

## Args and Envs

```text
  --host HOST           Host address to bind to
  --port PORT           Port to bind to
  --max-workers MAX_WORKERS
                        Number of worker threads (default: from MAX_WORKERS or CPU count)
  --tesseract-config TESSERACT_CONFIG
                        Custom Tesseract config flags (e.g. '-l rus+eng+ukr --oem 1 --psm 3')
  --pdf-dpi PDF_DPI     DPI resolution for rendering PDF pages to images (default: 200)
```
