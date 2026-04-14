# WordCountCalculator

WordCountCalculator is a small Python WSGI service that extracts text from uploaded files and returns a word count.

It supports:
- Images (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.tif`, `.tiff`, `.webp`) using Google Vision OCR
- PDF (`.pdf`) using text extraction, with Google Vision OCR fallback for scanned/non-copyable PDFs (and local OCR fallback if needed)
- Word documents (`.docx`, `.doc`)

## API Endpoints

- `GET /health`  
  Returns service status. Requires `X-API-Key` header.

- `POST /upload`  
  Accepts `multipart/form-data` with a `file` field and returns:
  - file name
  - save location
  - word count
  - short text preview
  Also requires `X-API-Key` header.

If upload payload is invalid, the API returns `400` with extra details such as:
- `received_content_type`
- `hint`

Example:

```bash
curl -i \
  -H "X-API-Key: your-api-key" \
  -X POST \
  -F "file=@/path/to/document.pdf" \
  http://wordcount.loc/upload
```

Health check example:

```bash
curl -i -H "X-API-Key: your-api-key" http://wordcount.loc/health
```

## Project Files

- `word_count_wsgi.py` - WSGI entry point and HTTP routing
- `word_count_core.py` - text extraction and word counting logic
- `apache-vhost-wordcount.conf.example` - Apache virtual host example

## Configuration

Optional environment variables:
- `CLOUD_VISION_API_KEY` - required for image OCR with Google Vision
- `VISION_ENDPOINT` - override Vision API endpoint (default is Google Vision annotate endpoint)
- `WORDCOUNT_FILES_DIR` - upload storage directory (if not set, app tries project `files/`, then `/tmp/wordcount-files`)
- `WORDCOUNT_API_KEY` - API key expected in the `X-API-Key` request header

You can place variables in a `.env` file in the project root.

## Logging

Debug logs are written to:
- `logs/debug.log` (inside the project root)

Logging is best-effort and will not break requests if the log file cannot be written.

## Local Setup

```bash
python3 -m venv .venv
.venv/bin/pip install requests pypdf python-docx pillow pytesseract pymupdf
```

For `.doc` support, install `antiword` or LibreOffice (`soffice`) on your system.
For OCR of scanned PDFs/images, set `CLOUD_VISION_API_KEY`.  
Optional local fallback: install Tesseract OCR binaries.

## Docker

Build and run with Docker Compose:

```bash
docker compose up --build -d
```

The container listens on:
- `http://localhost:8010`

Example health check:

```bash
curl -i -H "X-API-Key: your-api-key" http://localhost:8010/health
```

Example upload:

```bash
curl -i \
  -H "X-API-Key: your-api-key" \
  -X POST \
  -F "file=@/path/to/document.pdf" \
  http://localhost:8010/upload
```

Stop:

```bash
docker compose down
```

After code changes, rebuild to apply updates:

```bash
docker compose down
docker compose up --build -d
```

Or use the helper script to pull latest `main` and redeploy in one step:

```bash
./redeploy.sh
```

The script runs:
- `git pull origin main`
- `docker compose down`
- `docker compose up --build -d`

## Apache Reverse Proxy for `wordcount.loc`

If you want to access Docker through `http://wordcount.loc`, configure Apache as a reverse proxy to port `8010`.

1. `/etc/hosts` should include:

```text
127.0.0.1 wordcount.loc
```

2. Example Apache vhost:

```apache
<VirtualHost *:80>
    ServerName wordcount.loc
    ServerAdmin webmaster@localhost

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8010/
    ProxyPassReverse / http://127.0.0.1:8010/

    ErrorLog ${APACHE_LOG_DIR}/wordcount_error.log
    CustomLog ${APACHE_LOG_DIR}/wordcount_access.log combined
</VirtualHost>
```

3. Enable proxy modules and reload Apache:

```bash
sudo a2enmod proxy proxy_http
sudo systemctl reload apache2
```

4. Test:

```bash
curl -i -H "X-API-Key: your-api-key" http://wordcount.loc/health
```

## Apache (mod_wsgi) Notes

Use `apache-vhost-wordcount.conf.example` as a starting point, then update all paths to match your local project directory and virtual environment.

Make sure the Apache/mod_wsgi process user can write to the upload directory.
