from __future__ import annotations

import io

from docx import Document


def _read_size_pt(run) -> float:
    return run.font.size.pt


def extract_docx_styles(data: bytes) -> dict[str, object]:
    """Return a best-effort style summary from a DOCX: fonts, sizes, spacing."""
    doc = Document(io.BytesIO(data))

    fonts: dict[str, int] = {}
    sizes: list[float] = []
    heading_sizes: list[float] = []
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
        is_heading_style = "Heading" in style_name

        for run in para.runs:
            if run.font.name:
                fonts[run.font.name] = fonts.get(run.font.name, 0) + 1
            if run.font.size:
                try:
                    size_pt = _read_size_pt(run)
                except Exception:
                    continue
                sizes.append(size_pt)
                if is_heading_style or run.font.bold:
                    heading_sizes.append(size_pt)

    dominant_font = max(fonts, key=lambda k: fonts[k]) if fonts else "Calibri"
    body_size = round(sorted(sizes)[len(sizes) // 2]) if sizes else 11
    # Heading size: smallest bold/heading-styled size that's larger than body text,
    # capped at body+6pt to exclude title/name lines (typically 14pt+ above body).
    heading_candidates = [s for s in heading_sizes if body_size < s <= body_size + 6]
    heading_size = round(min(heading_candidates)) if heading_candidates else body_size
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
