from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path

try:
    from PIL import Image, ImageFilter, ImageOps
except Exception:  # pragma: no cover - optional dependency
    Image = None
    ImageFilter = None
    ImageOps = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency
    OpenAI = None


logger = logging.getLogger(__name__)


class OCRServiceError(RuntimeError):
    pass


def _safe_str(value) -> str:
    return "" if value is None else str(value)


def _get_openai_client():
    if OpenAI is None:
        raise OCRServiceError("openai package is not installed.")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OCRServiceError("OPENAI_API_KEY is missing.")

    return OpenAI(api_key=api_key)


def _build_data_url(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_text_with_openai(path: Path) -> str:
    client = _get_openai_client()
    data_url = _build_data_url(path)
    response = client.responses.create(
        model=os.getenv("OPENAI_OCR_MODEL", "gpt-4.1-mini"),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are reading a Korean school meal table image. Extract the visible meal-table text faithfully, "
                            "especially dates, weekday columns, menu names, and allergy numbers in parentheses. "
                            "Preserve useful line breaks and table relationships. Do not summarize."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": data_url,
                    },
                ],
            }
        ],
    )
    text = _safe_str(getattr(response, "output_text", "")).strip()
    if not text:
        raise OCRServiceError("OpenAI vision OCR returned empty text.")
    return text


def extract_text(image_path: str | os.PathLike[str], lang: str | None = None) -> str:
    path = Path(image_path)
    if not path.exists():
        raise OCRServiceError(f"OCR input file was not found: {path}")

    try:
        return _extract_text_with_openai(path)
    except Exception as exc:
        openai_error = _safe_str(exc).strip()
        logger.exception("OpenAI vision meal-table extraction failed")
        raise OCRServiceError(f"AI image extraction failed. OpenAI: {openai_error}") from exc
