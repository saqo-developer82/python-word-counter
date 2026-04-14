#!/usr/bin/env python3
from __future__ import annotations

import argparse
import cgi
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path

from word_count_core import (
    get_files_dir,
    get_script_dir,
    get_vision_endpoint,
    load_dotenv,
    process_file,
)


def parse_args(default_vision_endpoint: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HTTP upload entrypoint.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Server port (default: 8000).",
    )
    parser.add_argument(
        "--vision-endpoint",
        default=default_vision_endpoint,
        help=f"Google Vision endpoint (default: {default_vision_endpoint}).",
    )
    return parser.parse_args()


def run_upload_server(host: str, port: int, vision_endpoint: str) -> None:
    files_dir = get_files_dir()

    class UploadHandler(BaseHTTPRequestHandler):
        def _send_json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, {"status": "ok"})
                return
            self._send_json(404, {"error": "Use POST /upload with form-data file."})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/upload":
                self._send_json(404, {"error": "Unknown endpoint."})
                return

            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._send_json(
                    400,
                    {"error": "Content-Type must be multipart/form-data."},
                )
                return

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                },
            )
            if "file" not in form:
                self._send_json(400, {"error": "Missing form-data field: file"})
                return

            uploaded = form["file"]
            if not getattr(uploaded, "filename", ""):
                self._send_json(400, {"error": "Uploaded file has no filename."})
                return

            safe_name = Path(uploaded.filename).name
            destination = (files_dir / safe_name).resolve()
            destination.write_bytes(uploaded.file.read())

            try:
                text, words = process_file(destination, vision_endpoint)
            except Exception as exc:  # noqa: BLE001
                self._send_json(400, {"error": str(exc), "file_name": safe_name})
                return

            preview = " ".join(text.split())[:200] if text.strip() else ""
            self._send_json(
                200,
                {
                    "file_name": safe_name,
                    "saved_to": str(destination),
                    "word_count": words,
                    "preview": preview,
                },
            )

    server = HTTPServer((host, port), UploadHandler)
    print(f"Upload API listening on http://{host}:{port}")
    print("POST /upload with form-data key: file")
    server.serve_forever()


def main() -> int:
    load_dotenv(get_script_dir() / ".env")
    args = parse_args(get_vision_endpoint())
    run_upload_server(args.host, args.port, args.vision_endpoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
