"""Export enriched leads from the Supabase `leads` table to an xlsx blob.

Used by GET /leads/download (linked from the Teams notification card) so Matt
can grab a per-upload spreadsheet containing the enriched data — LinkedIn,
tenure, signal, opener, etc. — without touching the original raw upload.
"""
import io
import logging
from typing import Any

from openpyxl import Workbook

from app.databaseconnection import supabase_manager

logger = logging.getLogger(__name__)

LEADS_TABLE = "leads"

# Column ordering matches what Matt would expect to see on a cold-call sheet:
# basics first, then enrichment / opener at the right.
EXPORT_COLUMNS: list[tuple[str, str]] = [
    # (header_label, source_key) — source_key with "enrichment." prefix pulls from jsonb
    ("Name", "name"),
    ("Company", "company"),
    ("Title", "title"),
    ("Phone", "phone"),
    ("Email", "email"),
    ("City", "enrichment.city"),
    ("State", "enrichment.state"),
    ("LinkedIn URL", "enrichment.linkedin_url"),
    ("LinkedIn Headline", "enrichment.linkedin_headline"),
    ("LinkedIn Summary", "enrichment.linkedin_summary"),
    ("Website", "enrichment.website"),
    ("Tenure (months)", "enrichment.tenure_months"),
    ("Tenure Label", "enrichment.tenure_label"),
    ("Prior Company 1", "enrichment.prior_company_1"),
    ("Prior Company 2", "enrichment.prior_company_2"),
    ("Title Qualifier", "title_qualifier"),
    ("Signal Tag", "signal_tag"),
    ("Script Used", "enrichment.script_used"),
    ("Personalized Opener", "enrichment.personalized_opener"),
    ("Source File", "source_file"),
    ("Enrichment Status", "enrichment_status"),
    ("Enriched At", "enriched_at"),
]


def fetch_leads(source_file: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
    """Pull rows from the leads table, optionally filtered by source_file."""
    client = supabase_manager.get_client()
    if not client:
        raise RuntimeError("Supabase client unavailable")

    query = client.table(LEADS_TABLE).select("*").order("id")
    if source_file:
        query = query.eq("source_file", source_file)
    return query.limit(limit).execute().data or []


def leads_to_xlsx(rows: list[dict[str, Any]]) -> bytes:
    """Build an xlsx from leads-table rows."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Enriched Leads"

    headers = [label for label, _ in EXPORT_COLUMNS]
    ws.append(headers)

    for row in rows:
        enrichment = row.get("enrichment") or {}
        values: list[Any] = []
        for _, key in EXPORT_COLUMNS:
            if key.startswith("enrichment."):
                values.append(enrichment.get(key.split(".", 1)[1], ""))
            else:
                values.append(row.get(key, ""))
        # openpyxl rejects dict/list cells; coerce non-scalars to strings.
        ws.append([_coerce_cell(v) for v in values])

    # Light column-width auto-fit so the sheet is readable when Matt opens it.
    for i, _ in enumerate(EXPORT_COLUMNS, start=1):
        col_letter = ws.cell(row=1, column=i).column_letter
        max_len = max(
            (len(str(cell.value)) for cell in ws[col_letter] if cell.value is not None),
            default=10,
        )
        ws.column_dimensions[col_letter].width = min(max_len + 2, 60)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _coerce_cell(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return str(v)
    return v
