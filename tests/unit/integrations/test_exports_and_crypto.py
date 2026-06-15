from __future__ import annotations

import pytest

from packages.export.docx_export import export_docx, export_txt
from packages.export.pdf_ingest import extract_text_from_upload
from packages.integrations.crypto.nowpayments import verify_ipn_signature


def test_export_txt():
    assert export_txt("hello").decode() == "hello"


def test_export_docx():
    data = export_docx("line1\nline2")
    assert data[:2] == b"PK"


def test_extract_txt():
    text = extract_text_from_upload("resume.txt", b"Hello resume")
    assert "Hello" in text


def test_crypto_signature_local():
    assert verify_ipn_signature(b"{}", "any") is True
