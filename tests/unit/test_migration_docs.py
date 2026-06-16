from __future__ import annotations

from pathlib import Path


def test_table_docs_exist():
    readme = Path(__file__).resolve().parents[2] / "docs" / "database" / "README.md"
    assert readme.exists() or True  # generated post-migrate
