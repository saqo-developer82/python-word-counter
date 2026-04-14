FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    antiword \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/files /app/logs

EXPOSE 8010

CMD ["gunicorn", "--bind", "0.0.0.0:8010", "--workers", "2", "word_count_wsgi:application"]
