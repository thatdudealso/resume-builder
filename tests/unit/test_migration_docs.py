from __future__ import annotations

from pathlib import Path

import packages.db.models  # noqa: F401
from packages.db.base import Base

ROOT = Path(__file__).resolve().parents[2]


def test_database_docs_cover_model_tables():
    tables_dir = ROOT / "docs" / "database" / "tables"
    readme = ROOT / "docs" / "database" / "README.md"
    schema = ROOT / "docs" / "database" / "schema.sql"
    table_names = sorted(Base.metadata.tables)

    assert readme.exists()
    assert schema.exists()
    assert sorted(path.stem for path in tables_dir.glob("*.md")) == table_names

    readme_text = readme.read_text()
    schema_text = schema.read_text()
    for table_name in table_names:
        assert f"tables/{table_name}.md" in readme_text
        assert f"CREATE TABLE public.{table_name}" in schema_text
