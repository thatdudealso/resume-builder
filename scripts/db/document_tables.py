#!/usr/bin/env python3
"""Regenerate docs/database/tables/*.md from SQLAlchemy models."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TABLES_DIR = ROOT / "docs" / "database" / "tables"
README = ROOT / "docs" / "database" / "README.md"

TABLE_PURPOSES = {
    "users": "Application users with free trial tracking.",
    "device_sessions": "Device fingerprint and IP hash per login session.",
    "refresh_tokens": "Rotating refresh tokens for JWT auth.",
    "master_resumes": "Uploaded master resume files and parsed text.",
    "agent_runs": "Resume tailoring runs with paywall lock state.",
    "agent_run_events": "SSE and audit events per agent run.",
    "payments": "Unified Stripe and crypto one-time payments.",
    "crypto_payments": "On-chain payment details for crypto unlocks.",
    "crypto_webhook_events": "Idempotent crypto webhook event log.",
    "stripe_events": "Idempotent Stripe webhook event log.",
    "exports": "Generated export files (TXT/DOCX/PDF).",
}


def main() -> None:
    import packages.db.models  # noqa: F401
    from packages.db.base import Base

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    table_names: list[str] = []
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        name = table.name
        table_names.append(name)
        lines = [
            f"# Table: `{name}`",
            "",
            TABLE_PURPOSES.get(name, "Application table."),
            "",
            "## Columns",
            "",
            "| Column | Type | Nullable |",
            "|--------|------|----------|",
        ]
        for col in table.columns:
            lines.append(f"| `{col.name}` | {col.type} | {col.nullable} |")
        lines.extend(["", "## Indexes", ""])
        if table.indexes:
            for idx in table.indexes:
                cols = ", ".join(c.name for c in idx.columns)
                lines.append(f"- `{idx.name}` on ({cols})")
        else:
            lines.append("- _(none beyond PK)_")
        lines.extend(["", "## Foreign Keys", ""])
        if table.foreign_keys:
            for fk in table.foreign_keys:
                lines.append(f"- `{fk.parent.name}` → `{fk.column.table.name}.{fk.column.name}`")
        else:
            lines.append("- _(none)_")
        lines.extend(
            [
                "",
                "## Example Query",
                "",
                "```sql",
                f"SELECT * FROM {name} LIMIT 10;",
                "```",
                "",
            ]
        )
        (TABLES_DIR / f"{name}.md").write_text("\n".join(lines))

    readme_lines = [
        "# Database Schema",
        "",
        "Auto-generated table documentation. Regenerate after migrations:",
        "",
        "```bash",
        "python scripts/db/document_tables.py",
        "```",
        "",
        "## Tables",
        "",
    ]
    for name in table_names:
        readme_lines.append(f"- [{name}](tables/{name}.md)")
    readme_lines.extend(["", "## ER Overview", "", "```mermaid", "erDiagram"])
    readme_lines.append("    users ||--o{ device_sessions : has")
    readme_lines.append("    users ||--o{ master_resumes : uploads")
    readme_lines.append("    users ||--o{ agent_runs : runs")
    readme_lines.append("    users ||--o{ payments : pays")
    readme_lines.append("    agent_runs ||--o| payments : unlocks")
    readme_lines.append("    payments ||--o| crypto_payments : details")
    readme_lines.append("```")
    README.parent.mkdir(parents=True, exist_ok=True)
    README.write_text("\n".join(readme_lines) + "\n")
    print(f"Documented {len(table_names)} tables in {TABLES_DIR}")


if __name__ == "__main__":
    main()
