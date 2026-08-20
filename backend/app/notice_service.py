import asyncio
from pathlib import Path

from pypdf import PdfReader


def extract_pdf(path: Path) -> tuple[str, dict]:
    reader = PdfReader(path)
    metadata = reader.metadata or {}
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text, {
        "page_count": len(reader.pages),
        "is_encrypted": reader.is_encrypted,
        "title": metadata.title,
        "author": metadata.author,
        "producer": metadata.producer,
        "text_length": len(text),
    }


async def extract_pdf_async(path: Path) -> tuple[str, dict]:
    return await asyncio.to_thread(extract_pdf, path)
