from __future__ import annotations

import html
import io
import textwrap


def _page_size_from_pdf(original_bytes: bytes | None) -> tuple[float, float]:
    if not original_bytes:
        return 612.0, 792.0
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(original_bytes)) as pdf:
            first_page = pdf.pages[0] if pdf.pages else None
            if first_page is None:
                return 612.0, 792.0
            return round(float(first_page.width), 2), round(float(first_page.height), 2)
    except Exception:
        return 612.0, 792.0


def _pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_object(number: int, body: str | bytes) -> bytes:
    payload = body.encode("latin-1") if isinstance(body, str) else body
    return b"%d 0 obj\n" % number + payload + b"\nendobj\n"


def _plain_pdf(plain_text: str, *, page_size: tuple[float, float]) -> bytes:
    width, height = page_size
    margin = 54.0
    font_size = 10
    line_height = 14
    max_chars = max(40, int((width - (margin * 2)) / 5.4))
    max_lines = max(1, int((height - (margin * 2)) / line_height))
    lines: list[str] = []
    for raw_line in plain_text.splitlines() or [""]:
        wrapped = textwrap.wrap(raw_line, width=max_chars, replace_whitespace=False) or [""]
        lines.extend(wrapped)

    pages = [lines[index : index + max_lines] for index in range(0, len(lines), max_lines)]
    if not pages:
        pages = [[""]]

    objects: list[bytes] = []
    page_object_numbers: list[int] = []
    next_object = 4
    for page_lines in pages:
        content_lines = [f"BT /F1 {font_size} Tf {margin:.2f} {height - margin:.2f} Td"]
        for index, line in enumerate(page_lines):
            if index:
                content_lines.append(f"0 -{line_height} Td")
            content_lines.append(f"({_pdf_text(line)}) Tj")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", errors="replace")
        stream_object = next_object
        page_object = next_object + 1
        next_object += 2
        page_object_numbers.append(page_object)
        objects.append(
            _pdf_object(
                stream_object,
                b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            )
        )
        objects.append(
            _pdf_object(
                page_object,
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.2f} {height:.2f}] "
                    f"/Resources << /Font << /F1 3 0 R >> >> /Contents {stream_object} 0 R >>"
                ),
            )
        )

    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    header_objects = [
        _pdf_object(1, "<< /Type /Catalog /Pages 2 0 R >>"),
        _pdf_object(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_numbers)} >>"),
        _pdf_object(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    all_objects = header_objects + objects

    output = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = [0]
    for item in all_objects:
        offsets.append(len(output))
        output.extend(item)
    xref_start = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(output)


def export_pdf(
    plain_text: str,
    *,
    original_filename: str | None = None,
    original_bytes: bytes | None = None,
) -> bytes:
    page_size = (
        _page_size_from_pdf(original_bytes)
        if (original_filename or "").lower().endswith(".pdf")
        else (612.0, 792.0)
    )
    page_css = f"@page {{ size: {page_size[0]}pt {page_size[1]}pt; margin: 0.6in; }}"
    document = f"""
    <html>
      <head>
        <style>
          {page_css}
          body {{
            color: #111;
            font-family: Arial, sans-serif;
            font-size: 10.5pt;
            line-height: 1.35;
            white-space: pre-wrap;
          }}
          pre {{
            font: inherit;
            white-space: pre-wrap;
            margin: 0;
          }}
        </style>
      </head>
      <body><pre>{html.escape(plain_text)}</pre></body>
    </html>
    """
    try:
        from weasyprint import HTML

        return HTML(string=document).write_pdf()
    except (ImportError, OSError):
        return _plain_pdf(plain_text, page_size=page_size)
