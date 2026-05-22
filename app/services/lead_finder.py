"""Find leads in the Supabase `leads` table by name.

Schema (see sql/create_leads_table.sql):
  - top-level columns: id, name, company, title, phone, email,
                       signal_tag, title_qualifier, source_file, timestamps
  - enrichment (jsonb): city, state, linkedin_*, tenure_*, prior_company_*,
                        script_used, personalized_opener

The public API (find_lead_by_name + row_to_lead_record) returns the same dict
shape the Excel-backed version used, so copilot.py / copilot_service.py don't
need to know the data source moved.
"""
import logging
from app.databaseconnection import supabase_manager

logger = logging.getLogger(__name__)

LEADS_TABLE = "leads"


def find_lead_by_name(name_query: str) -> dict | None:
    """Return the first lead whose name matches (case-insensitive).

    Tries exact lower(name) match first; falls back to a substring ILIKE search.
    Returns the raw row dict (Supabase row) or None.
    """
    if not name_query or not name_query.strip():
        return None

    client = supabase_manager.get_client()
    if not client:
        logger.error("Supabase client unavailable — cannot look up leads")
        return None

    query = name_query.strip()

    # Exact match first (cheap, indexed via leads_name_lower_idx).
    exact = (
        client.table(LEADS_TABLE)
        .select("*")
        .ilike("name", query)
        .limit(1)
        .execute()
    )
    if exact.data:
        return exact.data[0]

    # Substring fallback: matches "John" against "John Smith".
    like = (
        client.table(LEADS_TABLE)
        .select("*")
        .ilike("name", f"%{query}%")
        .limit(1)
        .execute()
    )
    return like.data[0] if like.data else None


def row_to_lead_record(row: dict) -> dict:
    """Normalize a Supabase row into the LeadRecord shape the Copilot API returns.

    Flattens the `enrichment` jsonb into top-level keys so every enrichment
    field is visible alongside the basics. Empty values are returned as ""
    (or None for integers) so Matt sees the field even when SerpAPI didn't
    find data — that way he can tell "no LinkedIn found" apart from
    "lookup was never run".
    """
    enrichment = row.get("enrichment") or {}
    return {
        # ── Identity / contact basics ────────────────────────────────────
        "row": row.get("id"),
        "name": row.get("name", "") or "",
        "company": row.get("company", "") or "",
        "title": row.get("title", "") or "",
        "phone": row.get("phone", "") or "",
        "email": row.get("email", "") or "",
        "city": enrichment.get("city", "") or "",
        "state": enrichment.get("state", "") or "",
        # ── From the uploaded file (when present, used to ground SerpAPI) ─
        "industry": enrichment.get("industry", "") or "",
        "department": enrichment.get("department", "") or "",
        # ── SerpAPI-derived enrichment ───────────────────────────────────
        "website": enrichment.get("website", "") or "",
        "location": enrichment.get("location", "") or "",
        "description": enrichment.get("description", "") or "",
        "linkedin_url": enrichment.get("linkedin_url", "") or "",
        "linkedin_headline": enrichment.get("linkedin_headline", "") or "",
        "linkedin_summary": enrichment.get("linkedin_summary", "") or "",
        "linkedin_company_description":
            enrichment.get("linkedin_company_description", "") or "",
        # ── LLM-derived signals ──────────────────────────────────────────
        "tenure_months": _as_int_or_none(enrichment.get("tenure_months")),
        "tenure_label": enrichment.get("tenure_label", "") or "",
        "prior_company_1": enrichment.get("prior_company_1", "") or "",
        "prior_company_2": enrichment.get("prior_company_2", "") or "",
        "title_qualifier": row.get("title_qualifier", "") or "",
        "signal_tag": row.get("signal_tag", "") or "",
        # ── Generated opener ─────────────────────────────────────────────
        "script_used": enrichment.get("script_used", "") or "",
        "personalized_opener": enrichment.get("personalized_opener", "") or "",
        # ── Enrichment metadata (so Matt can see "is this fresh data?") ──
        "enrichment_status": row.get("enrichment_status", "") or "",
        "enrichment_attempts": row.get("enrichment_attempts") or 0,
        "enrichment_error": row.get("enrichment_error", "") or "",
        "enriched_at": row.get("enriched_at", "") or "",
        "source_file": row.get("source_file", "") or "",
        "created_at": row.get("created_at", "") or "",
        "updated_at": row.get("updated_at", "") or "",
    }


def _as_int_or_none(v) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
