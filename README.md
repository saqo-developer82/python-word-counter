# WordCountCalculator

WordCountCalculator is a small Python WSGI service that extracts text from uploaded files and returns a word count.

It supports:
- Images (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`) using Google Vision OCR
- PDF (`.pdf`) using text extraction, with local OCR fallback for scanned PDFs
- Word documents (`.docx`, `.doc`)

## API Endpoints

- `GET /health`  
  Returns service status.

- `POST /upload`  
  Accepts `multipart/form-data` with a `file` field and returns:
  - file name
  - save location
  - word count
  - short text preview

Example:

```bash
curl -i -X POST -F "file=@/path/to/document.pdf" http://wordcount.loc/upload
```

## Project Files

- `word_count_wsgi.py` - WSGI entry point and HTTP routing
- `word_count_core.py` - text extraction and word counting logic
- `apache-vhost-wordcount.conf.example` - Apache virtual host example

## Configuration

Optional environment variables:
- `CLOUD_VISION_API_KEY` - required for image OCR with Google Vision
- `VISION_ENDPOINT` - override Vision API endpoint
- `WORDCOUNT_FILES_DIR` - upload storage directory (if not set, app tries project `files/`, then `/tmp/wordcount-files`)

You can place variables in a `.env` file in the project root.

## Local Setup

```bash
python3 -m venv .venv
.venv/bin/pip install requests pypdf python-docx pillow pytesseract pymupdf
```

For `.doc` support, install `antiword` on your system.
For OCR of scanned PDFs/images, install Tesseract OCR binaries.

## Apache (mod_wsgi) Notes

Use `apache-vhost-wordcount.conf.example` as a starting point, then update all paths to match your local project directory and virtual environment.

Make sure the Apache/mod_wsgi process user can write to the upload directory.
