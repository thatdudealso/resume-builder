from __future__ import annotations

import io
import re

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

_SECTION_HEADERS = {"SUMMARY", "EXPERIENCE", "SKILLS", "EDUCATION"}
_BULLET_PATTERN = re.compile(r"^(\s*[-•*]\s+)(.*)")


def _set_font(run, name: str, size_pt: float, bold: bool = False) -> None:
    run.font.name = name
    run.font.size = Pt(size_pt)
    run.font.bold = bold


def _add_horizontal_rule(paragraph) -> None:
    """Insert a bottom-border on the paragraph to act as a section divider."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "CCCCCC")
    pBdr.append(bottom)
    pPr.append(pBdr)


def export_docx(plain_text: str, style_metadata: dict | None = None) -> bytes:
    meta = style_metadata or {}
    font = meta.get("font", "Calibri")
    body_size = float(meta.get("body_size_pt", 11))
    heading_size = float(meta.get("heading_size_pt", body_size + 2))
    space_before = int(meta.get("space_before_pt", 4))
    space_after = int(meta.get("space_after_pt", 4))

    doc = Document()

    # Remove default margins to give clean page
    for section in doc.sections:
        section.top_margin = Pt(36)
        section.bottom_margin = Pt(36)
        section.left_margin = Pt(54)
        section.right_margin = Pt(54)

    for line in plain_text.splitlines():
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph()
            continue

        is_header = stripped.upper() in _SECTION_HEADERS
        bullet_match = _BULLET_PATTERN.match(stripped)

        if is_header:
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(space_before + 4)
            para.paragraph_format.space_after = Pt(2)
            run = para.add_run(stripped.upper())
            _set_font(run, font, heading_size, bold=True)
            run.font.color.rgb = RGBColor(0x2F, 0x6F, 0x5F)
            _add_horizontal_rule(para)
        elif bullet_match:
            bullet_text = bullet_match.group(2)
            para = doc.add_paragraph(style="List Bullet")
            para.paragraph_format.space_before = Pt(space_before)
            para.paragraph_format.space_after = Pt(space_after)
            run = para.add_run(bullet_text)
            _set_font(run, font, body_size)
        else:
            para = doc.add_paragraph()
            para.paragraph_format.space_before = Pt(space_before)
            para.paragraph_format.space_after = Pt(space_after)
            run = para.add_run(stripped)
            _set_font(run, font, body_size)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_txt(plain_text: str) -> bytes:
    return plain_text.encode("utf-8")
