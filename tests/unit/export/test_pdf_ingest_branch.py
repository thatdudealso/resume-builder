from __future__ import annotations

import pytest

from packages.export.pdf_ingest import extract_text_from_upload


def test_extract_pdf_branch(monkeypatch):
    monkeypatch.setattr(
        "packages.export.pdf_ingest.extract_text_from_pdf",
        lambda data: "PDF resume text",
    )
    text = extract_text_from_upload("resume.pdf", b"%PDF-fake")
    assert text == "PDF resume text"
