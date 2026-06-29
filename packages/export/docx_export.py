from __future__ import annotations

import io

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def _clear_paragraph(paragraph: Paragraph) -> None:
    for run in list(paragraph.runs):
        paragraph._p.remove(run._r)


def _remove_paragraph(paragraph: Paragraph) -> None:
    element = paragraph._element
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _iter_table_paragraphs(table: Table) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    for row in table.rows:
        for cell in row.cells:
            paragraphs.extend(cell.paragraphs)
            for nested_table in cell.tables:
                paragraphs.extend(_iter_table_paragraphs(nested_table))
    return paragraphs


def _iter_body_paragraphs(doc: DocxDocument) -> list[tuple[Paragraph, bool]]:
    paragraphs: list[tuple[Paragraph, bool]] = []
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            paragraphs.append((Paragraph(child, doc), True))
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            paragraphs.extend((paragraph, False) for paragraph in _iter_table_paragraphs(table))
    return paragraphs


def _populate_plain_docx(doc: DocxDocument, plain_text: str) -> bytes:
    for line in plain_text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _populate_template_docx(doc: DocxDocument, plain_text: str) -> bytes:
    lines = plain_text.splitlines()
    paragraphs = _iter_body_paragraphs(doc)
    last_style = paragraphs[-1][0].style if paragraphs else None

    for index, line in enumerate(lines):
        if index < len(paragraphs):
            paragraph = paragraphs[index][0]
            _clear_paragraph(paragraph)
            paragraph.add_run(line)
        else:
            doc.add_paragraph(line, style=last_style)

    for paragraph, can_remove in paragraphs[len(lines) :]:
        if can_remove:
            _remove_paragraph(paragraph)
        else:
            _clear_paragraph(paragraph)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_docx(plain_text: str, template_bytes: bytes | None = None) -> bytes:
    if template_bytes:
        try:
            return _populate_template_docx(Document(io.BytesIO(template_bytes)), plain_text)
        except Exception:
            pass
    return _populate_plain_docx(Document(), plain_text)


def export_txt(plain_text: str) -> bytes:
    return plain_text.encode("utf-8")
