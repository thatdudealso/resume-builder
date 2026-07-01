from __future__ import annotations

import io
import re
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

from packages.agent.schemas.variants import SECTION_KEYS

_SECTION_HEADERS = {k.upper() for k in SECTION_KEYS}
_BULLET_PATTERN = re.compile(r"^(\s*[-•*]\s+)(.*)")


def _str_meta(meta: dict[str, object], key: str, default: str) -> str:
    value = meta.get(key, default)
    return value if isinstance(value, str) else default


def _float_meta(meta: dict[str, object], key: str, default: float) -> float:
    value = meta.get(key, default)
    if isinstance(value, str | int | float):
        return float(value)
    return default


def _int_meta(meta: dict[str, object], key: str, default: int) -> int:
    value = meta.get(key, default)
    if isinstance(value, str | int | float):
        return int(value)
    return default


def _set_font(run: Any, name: str, size_pt: float, bold: bool = False) -> None:
    run.font.name = name
    run.font.size = Pt(size_pt)
    run.font.bold = bold


def _add_horizontal_rule(paragraph: Any) -> None:
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


def export_docx(plain_text: str, style_metadata: dict[str, object] | None = None) -> bytes:
    meta = style_metadata or {}
    font = _str_meta(meta, "font", "Calibri")
    body_size = _float_meta(meta, "body_size_pt", 11)
    heading_size = _float_meta(meta, "heading_size_pt", body_size + 2)
    space_before = _int_meta(meta, "space_before_pt", 4)
    space_after = _int_meta(meta, "space_after_pt", 4)

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
