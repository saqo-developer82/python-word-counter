from __future__ import annotations

import base64
from io import BytesIO
import os
from pathlib import Path
import re
import subprocess
import tempfile

import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - runtime dependency check
    PdfReader = None

try:
    import fitz
except ImportError:  # pragma: no cover - runtime dependency check
    fitz = None

try:
    from docx import Document
except ImportError:  # pragma: no cover - runtime dependency check
    Document = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - runtime dependency check
    Image = None

try:
    import pytesseract
except ImportError:  # pragma: no cover - runtime dependency check
    pytesseract = None


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
PDF_SUFFIXES = {".pdf"}
DOCX_SUFFIXES = {".docx"}
DOC_SUFFIXES = {".doc"}
VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
_CJK_CHAR_RE = re.compile(
    "["
    "\u3040-\u309f"
    "\u30a0-\u30ff"
    "\u31f0-\u31ff"
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "]"
)


def count_words(text: str) -> int:
    if not text:
        return 0
    cjk_units = len(_CJK_CHAR_RE.findall(text))
    remainder = _CJK_CHAR_RE.sub(" ", text)
    western_tokens = len(
        re.findall(r"[A-Za-z][A-Za-z0-9'.-]*|[0-9][0-9,.'-]*", remainder)
    )
    return cjk_units + western_tokens


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def get_files_dir() -> Path:
    configured = os.getenv("WORDCOUNT_FILES_DIR", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(get_script_dir() / "files")
    candidates.append(Path(tempfile.gettempdir()) / "wordcount-files")

    for candidate in candidates:
        path = candidate.resolve()
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return path
        except OSError:
            continue

    raise RuntimeError("No writable files directory available for uploads.")


def resolve_allowed_path(file_name: str) -> Path:
    files_dir = get_files_dir()

    if Path(file_name).name != file_name:
        raise ValueError("Provide only the file name, not a path.")

    input_path = (files_dir / file_name).resolve()
    try:
        input_path.relative_to(files_dir)
    except ValueError as exc:
        raise ValueError(f"File must be located inside: {files_dir}") from exc
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")
    return input_path


def normalize_vision_endpoint(endpoint: str) -> str:
    endpoint = endpoint.strip()
    if endpoint.endswith("/v1/images"):
        return f"{endpoint}:annotate"
    return endpoint


def get_vision_endpoint() -> str:
    return os.getenv("VISION_ENDPOINT", VISION_ENDPOINT)


def extract_text_from_pdf(path: Path) -> str:
    if PdfReader is not None:
        reader = PdfReader(str(path))
        chunks: list[str] = []
        for page in reader.pages:
            chunks.append(page.extract_text() or "")
        return "\n".join(chunks)

    if fitz is not None:
        chunks = []
        with fitz.open(str(path)) as document:
            for page in document:
                chunks.append(page.get_text("text") or "")
        return "\n".join(chunks)

    raise RuntimeError("Missing dependency: install pypdf (or PyMuPDF).")


def extract_text_from_pdf_local_ocr(path: Path) -> str:
    if fitz is None:
        raise RuntimeError(
            "Scanned PDF local OCR requires PyMuPDF (fitz) to render pages."
        )
    if Image is None:
        raise RuntimeError("Scanned PDF local OCR requires Pillow.")
    if pytesseract is None:
        raise RuntimeError("Scanned PDF local OCR requires pytesseract.")

    page_texts: list[str] = []
    with fitz.open(str(path)) as document:
        for page in document:
            pix = page.get_pixmap(dpi=300)
            image = Image.open(BytesIO(pix.tobytes("png")))
            page_text = pytesseract.image_to_string(image, lang="jpn+eng")
            if page_text.strip():
                page_texts.append(page_text)
    return "\n".join(page_texts)


def extract_text_from_docx(path: Path) -> str:
    if Document is None:
        raise RuntimeError("Missing dependency: install python-docx")
    document = Document(str(path))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def extract_text_from_doc(path: Path) -> str:
    antiword_cmd = ["antiword", str(path)]
    try:
        result = subprocess.run(
            antiword_cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.strip() or "Failed to parse .doc file.") from exc

    # Fallback path when antiword is unavailable.
    # LibreOffice can convert legacy .doc to plain text in headless mode.
    with tempfile.TemporaryDirectory(prefix="wordcount-doc-") as tmp_dir:
        output_dir = Path(tmp_dir)
        cmd = [
            "soffice",
            "--headless",
            "--convert-to",
            "txt:Text",
            "--outdir",
            str(output_dir),
            str(path),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Legacy .doc requires antiword or LibreOffice (soffice). Install one and retry."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                exc.stderr.strip() or "Failed to convert .doc file with LibreOffice."
            ) from exc

        converted = output_dir / f"{path.stem}.txt"
        if not converted.exists():
            raise RuntimeError("LibreOffice conversion did not produce a text output file.")
        return converted.read_text(encoding="utf-8", errors="ignore")


def extract_text_with_google_vision(path: Path, endpoint: str) -> str:
    api_key = os.getenv("CLOUD_VISION_API_KEY")
    if not api_key:
        raise RuntimeError("Set CLOUD_VISION_API_KEY in .env before processing images.")

    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    payload = {
        "requests": [
            {
                "image": {"content": encoded},
                "features": [{"type": "TEXT_DETECTION"}],
            }
        ]
    }
    response = requests.post(
        normalize_vision_endpoint(endpoint),
        params={"key": api_key},
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Vision API request failed ({response.status_code}): {response.text}"
        )

    body = response.json()
    responses = body.get("responses", [])
    if not responses:
        return ""
    annotation = responses[0].get("fullTextAnnotation", {})
    return annotation.get("text", "")


def process_file(path: Path, vision_endpoint: str) -> tuple[str, int]:
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        text = extract_text_with_google_vision(path, vision_endpoint)
    elif suffix in PDF_SUFFIXES:
        text = extract_text_from_pdf(path)
        if not text.strip():
            text = extract_text_from_pdf_local_ocr(path)
    elif suffix in DOCX_SUFFIXES:
        text = extract_text_from_docx(path)
    elif suffix in DOC_SUFFIXES:
        text = extract_text_from_doc(path)
    else:
        raise ValueError(
            f"Unsupported file type: {suffix or 'unknown'}. Use image/pdf/doc/docx."
        )
    return text, count_words(text)
