#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from word_count_core import (
    get_script_dir,
    get_vision_endpoint,
    load_dotenv,
    process_file,
    resolve_allowed_path,
)


def parse_args(default_vision_endpoint: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI word count entrypoint.")
    parser.add_argument(
        "file_name",
        help="File name inside WordCountCalculator/files (example: sample.pdf).",
    )
    parser.add_argument(
        "--vision-endpoint",
        default=default_vision_endpoint,
        help=f"Google Vision endpoint (default: {default_vision_endpoint}).",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(get_script_dir() / ".env")
    args = parse_args(get_vision_endpoint())
    try:
        input_path = resolve_allowed_path(args.file_name)
        text, words = process_file(input_path, args.vision_endpoint)
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"File: {input_path}")
    print(f"Word count: {words}")
    if text.strip():
        preview = " ".join(text.split())[:200]
        print(f"Preview: {preview}")
    else:
        print("Preview: <no text detected>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
