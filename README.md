# Anydocte

This repo provides an external document extraction service for integration of anydoc with openwebui.  
But it has a FAST/REST API, thus it can be used anywhere.

Anydoc can't do OCR, so pdf_inspector is used to check if PDF needs OCR, than tesseract runs if needed.

File types are detected from the **content** with libmagic, not from the
filename, so a mislabeled upload still takes the right path:

 | Detected type                               | Handling                                                    |
 | ---                                         | ---                                                         |
 | png/jpg/jpeg/tiff/bmp/webp                  | Tesseract OCR                                               |
 | pdf                                         | pdf_inspector; OCR only for scanned/mixed pages             |
 | csv                                         | anydoc → markdown (falls back to plain text if unparseable) |
 | doc/docx/odt/ppt/pptx/rtf/epub/xlsx/ods/odp | anydoc → markdown                                           |
 | any other `text/*`                          | decoded as UTF-8 directly                                   |
 | anything else                               | rejected as unsupported                                     |

> [!note]
> legacy **`.xls`** (Excel 97–2003) is *not* supported — anydoc has no `xls`
> format — so those uploads return empty content rather than an error.
> Convert them to `.xlsx` first.


## Dependencies

- System:
    - tesseract-ocr
    - poppler-utils
    - libmagic (the `file` package; `python-magic` loads it at runtime)
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

It implies that tesseract, poppler-utils and libmagic already installed

```bash
# install the package with dependencies in a venv
python -m venv venv
./venv/bin/pip install -e .

# if you get "ImportError: failed to find libmagic", point the loader at it,
# e.g. on NixOS:  export LD_LIBRARY_PATH=$(dirname $(readlink -f $(which file)))/../lib

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
  anydocte:0.3.0-full
```


### 2. Set settings in openwebui

1. Admin -> Settings -> Documents -> Select "External"
2. Fill "Document Loader URL"
3. Fill some random symbols in "API key"
4. Add `image/*` to "Supported Media MIME Types"

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
