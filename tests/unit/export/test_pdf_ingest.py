from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@patch("packages.export.pdf_ingest.pdfplumber.open")
def test_extract_pdf(mock_open):
    page = MagicMock()
    page.extract_text.return_value = "PDF resume text"
    mock_open.return_value.__enter__.return_value.pages = [page]
    from packages.export.pdf_ingest import extract_text_from_pdf

    text = extract_text_from_pdf(b"%PDF")
    assert "PDF resume" in text


def test_unsupported_format():
    from packages.export.pdf_ingest import extract_text_from_upload

    with pytest.raises(ValueError):
        extract_text_from_upload("file.doc", b"x")
