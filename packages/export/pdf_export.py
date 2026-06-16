from __future__ import annotations


def export_pdf(plain_text: str) -> bytes:
    from weasyprint import HTML

    html = (
        "<html><body><pre>"
        + plain_text.replace("&", "&amp;").replace("<", "&lt;")
        + "</pre></body></html>"
    )
    return HTML(string=html).write_pdf()
