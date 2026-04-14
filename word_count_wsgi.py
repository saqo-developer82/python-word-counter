from __future__ import annotations

import cgi
import json
from pathlib import Path
import time
from typing import Callable

from word_count_core import (
    get_files_dir,
    get_script_dir,
    get_vision_endpoint,
    load_dotenv,
    process_file,
)


load_dotenv(get_script_dir() / ".env")
DEBUG_LOG_PATH = Path("/home/developer/Documents/MyPythonCodes/.cursor/debug-9e73f9.log")
DEBUG_SESSION_ID = "9e73f9"


def _agent_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    # Never let debug logging break request handling in production.
    try:
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass


# region agent log
_agent_log(
    run_id="pre-fix",
    hypothesis_id="H1",
    location="word_count_wsgi.py:module",
    message="WSGI module imported",
    data={"script_dir": str(get_script_dir())},
)
# endregion


def _json_response(
    start_response: Callable,
    status: str,
    payload: dict[str, object],
) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    start_response(status, headers)
    return [body]


def _handle_upload(environ: dict, start_response: Callable) -> list[bytes]:
    # region agent log
    _agent_log(
        run_id="pre-fix",
        hypothesis_id="H3",
        location="word_count_wsgi.py:_handle_upload:entry",
        message="Entered upload handler",
        data={
            "content_type": environ.get("CONTENT_TYPE", ""),
            "content_length": environ.get("CONTENT_LENGTH", ""),
        },
    )
    # endregion
    content_type = environ.get("CONTENT_TYPE", "")
    if "multipart/form-data" not in content_type:
        return _json_response(
            start_response,
            "400 Bad Request",
            {"error": "Content-Type must be multipart/form-data."},
        )

    try:
        form = cgi.FieldStorage(
            fp=environ["wsgi.input"],
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": environ.get("CONTENT_LENGTH", "0"),
            },
        )
    except (ValueError, TypeError, OSError) as exc:
        return _json_response(
            start_response,
            "400 Bad Request",
            {"error": f"Invalid multipart payload: {exc}"},
        )

    if "file" not in form:
        return _json_response(
            start_response,
            "400 Bad Request",
            {"error": "Missing form-data field: file"},
        )

    uploaded = form["file"]
    if not getattr(uploaded, "filename", ""):
        return _json_response(
            start_response,
            "400 Bad Request",
            {"error": "Uploaded file has no filename."},
        )

    safe_name = Path(uploaded.filename).name
    destination = (get_files_dir() / safe_name).resolve()
    try:
        destination.write_bytes(uploaded.file.read())
    except OSError as exc:
        return _json_response(
            start_response,
            "500 Internal Server Error",
            {"error": f"Unable to store uploaded file: {exc}"},
        )
    # region agent log
    _agent_log(
        run_id="pre-fix",
        hypothesis_id="H4",
        location="word_count_wsgi.py:_handle_upload:save",
        message="Saved uploaded file",
        data={"file_name": safe_name, "destination": str(destination)},
    )
    # endregion

    try:
        text, words = process_file(destination, get_vision_endpoint())
    except Exception as exc:  # noqa: BLE001
        return _json_response(
            start_response,
            "400 Bad Request",
            {"error": str(exc), "file_name": safe_name},
        )

    preview = " ".join(text.split())[:200] if text.strip() else ""
    return _json_response(
        start_response,
        "200 OK",
        {
            "file_name": safe_name,
            "saved_to": str(destination),
            "word_count": words,
            "preview": preview,
        },
    )


def application(environ: dict, start_response: Callable) -> list[bytes]:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")
    # region agent log
    _agent_log(
        run_id="pre-fix",
        hypothesis_id="H2",
        location="word_count_wsgi.py:application:entry",
        message="WSGI request received",
        data={"method": method, "path": path},
    )
    # endregion

    if method == "GET" and path == "/health":
        return _json_response(start_response, "200 OK", {"status": "ok"})

    if method == "POST" and path == "/upload":
        return _handle_upload(environ, start_response)

    return _json_response(
        start_response,
        "404 Not Found",
        {"error": "Use GET /health or POST /upload"},
    )
