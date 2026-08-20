import asyncio
from pathlib import Path

import fitz
import pytesseract
from PIL import Image
from pypdf import PdfReader

from .config import get_settings


def extract_ocr(path: Path, page_count: int) -> tuple[str, dict]:
    settings = get_settings()
    document = fitz.open(path)
    pages, failures = [], []
    matrix = fitz.Matrix(settings.ocr_render_scale, settings.ocr_render_scale)
    try:
        for index, page in enumerate(document):
            try:
                pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                pages.append(pytesseract.image_to_string(image, lang=settings.ocr_languages, timeout=settings.ocr_timeout_seconds))
            except Exception:
                failures.append(index + 1)
    finally:
        document.close()
    text = "\n".join(pages).strip()
    return text, {"text_source": "ocr", "ocr_page_count": page_count, "ocr_pages_succeeded": page_count - len(failures), "ocr_failed_pages": failures, "ocr_languages": settings.ocr_languages, "ocr_text_length": len(text)}


def extract_pdf(path: Path) -> tuple[str, dict]:
    settings = get_settings()
    reader = PdfReader(path)
    metadata = reader.metadata or {}
    page_count = len(reader.pages)
    embedded_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    threshold = max(settings.ocr_min_embedded_chars, page_count * settings.ocr_min_embedded_chars_per_page)
    base = {"page_count": page_count, "is_encrypted": reader.is_encrypted, "title": metadata.title, "author": metadata.author, "producer": metadata.producer, "embedded_text_length": len(embedded_text), "ocr_threshold": threshold}
    if settings.ocr_enabled and len(embedded_text) < threshold:
        ocr_text, ocr_metadata = extract_ocr(path, page_count)
        if ocr_text:
            return ocr_text, {**base, **ocr_metadata, "text_length": len(ocr_text)}
        return embedded_text, {**base, **ocr_metadata, "text_source": "embedded_ocr_failed", "text_length": len(embedded_text)}
    return embedded_text, {**base, "text_source": "embedded", "text_length": len(embedded_text)}


async def extract_pdf_async(path: Path) -> tuple[str, dict]:
    return await asyncio.to_thread(extract_pdf, path)
