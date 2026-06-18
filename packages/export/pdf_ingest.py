from __future__ import annotations

import io

import pdfplumber
from docx import Document


def extract_text_from_pdf(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages).strip()


def extract_text_from_docx(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    return "\n".join(paragraph for paragraph in paragraphs if paragraph).strip()


def _require_resume_text(text: str) -> str:
    normalized = text.strip()
    if not normalized:
        raise ValueError("Resume file does not contain readable text.")
    return normalized


def extract_text_from_upload(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return _require_resume_text(extract_text_from_pdf(data))
    if lower.endswith(".docx"):
        return _require_resume_text(extract_text_from_docx(data))
    if lower.endswith(".txt"):
        return _require_resume_text(data.decode("utf-8", errors="ignore"))
    raise ValueError("Unsupported file type. Upload PDF, DOCX, or TXT.")
