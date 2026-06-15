from __future__ import annotations

import io

from docx import Document


def export_docx(plain_text: str) -> bytes:
    doc = Document()
    for line in plain_text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_txt(plain_text: str) -> bytes:
    return plain_text.encode("utf-8")
