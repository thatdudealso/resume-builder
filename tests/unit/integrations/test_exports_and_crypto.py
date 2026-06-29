from __future__ import annotations

import io

from docx import Document
from docx.shared import Pt

from packages.export.docx_export import export_docx, export_txt
from packages.export.pdf_ingest import extract_text_from_upload
from packages.export.style_extractor import extract_docx_styles
from packages.integrations.crypto.nowpayments import verify_ipn_signature


def test_export_txt():
    assert export_txt("hello").decode() == "hello"


def test_export_docx():
    data = export_docx("line1\nline2")
    assert data[:2] == b"PK"


def test_export_docx_applies_style_metadata():
    data = export_docx(
        "SUMMARY\n\n- Built Python APIs\nEXPERIENCE\nDelivered systems",
        style_metadata={
            "font": "Arial",
            "body_size_pt": "10",
            "heading_size_pt": 14,
            "space_before_pt": 3.5,
            "space_after_pt": 2,
        },
    )
    doc = Document(io.BytesIO(data))

    assert doc.paragraphs[0].text == "SUMMARY"
    assert doc.paragraphs[0].runs[0].bold is True
    assert doc.paragraphs[2].style.name == "List Bullet"
    assert doc.paragraphs[2].text == "Built Python APIs"
    assert doc.paragraphs[-1].text == "Delivered systems"


def test_export_docx_handles_invalid_style_metadata_defaults():
    data = export_docx(
        "SKILLS\nPython",
        style_metadata={
            "font": object(),
            "body_size_pt": object(),
            "space_before_pt": object(),
        },
    )
    doc = Document(io.BytesIO(data))

    assert doc.paragraphs[0].text == "SKILLS"
    assert doc.paragraphs[1].text == "Python"


def test_extract_docx_styles_reads_font_spacing_and_bullets():
    source = Document()
    paragraph = source.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(8)
    run = paragraph.add_run("Engineer")
    run.font.name = "Arial"
    run.font.size = Pt(11)
    source.add_paragraph("Built systems", style="List Bullet")
    buffer = io.BytesIO()
    source.save(buffer)

    styles = extract_docx_styles(buffer.getvalue())

    assert styles["font"] == "Arial"
    assert styles["body_size_pt"] == 11
    assert styles["heading_size_pt"] == 11
    assert styles["space_before_pt"] == 4
    assert styles["space_after_pt"] == 8
    assert styles["has_bullets"] is True


def test_extract_docx_styles_ignores_unreadable_run_sizes(monkeypatch):
    source = Document()
    run = source.add_paragraph().add_run("Engineer")
    run.font.size = Pt(11)
    buffer = io.BytesIO()
    source.save(buffer)

    def broken_pt(value):
        raise ValueError("bad size")

    monkeypatch.setattr("packages.export.style_extractor.Pt", broken_pt)

    styles = extract_docx_styles(buffer.getvalue())

    assert styles["body_size_pt"] == 11


def test_extract_txt():
    text = extract_text_from_upload("resume.txt", b"Hello resume")
    assert "Hello" in text


def test_crypto_signature_local(monkeypatch):
    """When no IPN secret is configured, verify_ipn_signature bypasses HMAC
    and returns True in local/test environments (no secret = bypass path)."""
    monkeypatch.setattr("apps.web.config.settings.nowpayments_ipn_secret", "")
    assert verify_ipn_signature(b"{}", "any") is True
