from __future__ import annotations

import io

from docx import Document
from docx.shared import Pt


def extract_docx_styles(data: bytes) -> dict:
    """Return a best-effort style summary from a DOCX: fonts, sizes, spacing."""
    doc = Document(io.BytesIO(data))

    fonts: dict[str, int] = {}
    sizes: list[float] = []
    space_before: list[float] = []
    space_after: list[float] = []
    has_bullets = False

    for para in doc.paragraphs:
        pf = para.paragraph_format
        if pf.space_before and pf.space_before.pt:
            space_before.append(pf.space_before.pt)
        if pf.space_after and pf.space_after.pt:
            space_after.append(pf.space_after.pt)
        style_name = para.style.name if para.style else ""
        if "List" in style_name or "Bullet" in style_name:
            has_bullets = True

        for run in para.runs:
            if run.font.name:
                fonts[run.font.name] = fonts.get(run.font.name, 0) + 1
            if run.font.size:
                try:
                    sizes.append(Pt(run.font.size.pt).pt)
                except Exception:
                    pass

    dominant_font = max(fonts, key=lambda k: fonts[k]) if fonts else "Calibri"
    body_size = round(sorted(sizes)[len(sizes) // 2]) if sizes else 11
    heading_size = max(sizes, default=body_size + 2)
    avg_space_before = round(sum(space_before) / len(space_before)) if space_before else 6
    avg_space_after = round(sum(space_after) / len(space_after)) if space_after else 6

    return {
        "font": dominant_font,
        "body_size_pt": body_size,
        "heading_size_pt": int(heading_size),
        "space_before_pt": avg_space_before,
        "space_after_pt": avg_space_after,
        "has_bullets": has_bullets,
    }
