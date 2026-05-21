"""Insert parsed Excel rows into the Supabase `leads` table.

Used by /webhooks/storage-uploaded when a new xlsx lands in the uploaded-leads
bucket. Maps the loose Excel column conventions (Name vs First+Last, Company vs
Account, etc.) onto the leads schema, then skips any rows whose (name, company)
pair already exists.
"""
import logging
from typing import Any

from app.databaseconnection import supabase_manager
from app.models.lead import LeadRow

logger = logging.getLogger(__name__)

LEADS_TABLE = "leads"

# Column-name candidates — handles the most common ZoomInfo / Apollo / generic
# export naming variations. Lowercased before matching.
NAME_COLS = ["name", "full name", "contact name", "lead name"]
FIRST_NAME_COLS = ["first name", "firstname", "given name"]
LAST_NAME_COLS = ["last name", "lastname", "surname", "family name"]
COMPANY_COLS = ["company", "company name", "account", "account name", "organization"]
TITLE_COLS = ["title", "job title", "position", "role"]
PHONE_COLS = ["phone", "phone number", "mobile", "direct phone", "work phone"]
EMAIL_COLS = ["email", "email address", "work email"]
CITY_COLS = ["city"]
STATE_COLS = ["state", "state/province", "region"]

# Maps Enriched_* column → key inside the enrichment jsonb blob.
ENRICHMENT_COL_MAP = {
    "enriched_linkedin": "linkedin_url",
    "enriched_linkedin_headline": "linkedin_headline",
    "enriched_linkedin_summary": "linkedin_summary",
    "enriched_tenure_months": "tenure_months",
    "enriched_tenure_label": "tenure_label",
    "enriched_prior_company_1": "prior_company_1",
    "enriched_prior_company_2": "prior_company_2",
    "enriched_script_used": "script_used",
    "enriched_personalized_opener": "personalized_opener",
}

# Enriched_* columns that get promoted to top-level lead table columns.
TOP_LEVEL_ENRICHED = {
    "enriched_title_qualifier": "title_qualifier",
    "enriched_signal_tag": "signal_tag",
}


def _lookup(data_lower: dict[str, str], candidates: list[str]) -> str:
    """Return the first non-empty value among the candidate column names."""
    for c in candidates:
        v = data_lower.get(c, "").strip()
        if v:
            return v
    return ""


def xlsx_row_to_lead_insert(row: LeadRow, source_file: str) -> dict[str, Any] | None:
    """Convert one parsed Excel row to a leads-table insert payload.

    Returns None if the row has no usable name (the one truly required field).
    """
    # Case-insensitive lookups — uploaded files have inconsistent casing.
    data_lower = {k.strip().lower(): (v or "") for k, v in row.data.items()}

    name = _lookup(data_lower, NAME_COLS)
    if not name:
        first = _lookup(data_lower, FIRST_NAME_COLS)
        last = _lookup(data_lower, LAST_NAME_COLS)
        name = f"{first} {last}".strip()
    if not name:
        return None

    company = _lookup(data_lower, COMPANY_COLS)
    title = _lookup(data_lower, TITLE_COLS)
    phone = _lookup(data_lower, PHONE_COLS)
    email = _lookup(data_lower, EMAIL_COLS)
    city = _lookup(data_lower, CITY_COLS)
    state = _lookup(data_lower, STATE_COLS)

    enrichment: dict[str, Any] = {}
    if city:
        enrichment["city"] = city
    if state:
        enrichment["state"] = state

    title_qualifier = ""
    signal_tag = ""

    # Map Enriched_* columns. Anything else we don't recognize goes into
    # enrichment["extras"] so no information is lost.
    extras: dict[str, str] = {}
    consumed = (
        set(NAME_COLS) | set(FIRST_NAME_COLS) | set(LAST_NAME_COLS)
        | set(COMPANY_COLS) | set(TITLE_COLS) | set(PHONE_COLS)
        | set(EMAIL_COLS) | set(CITY_COLS) | set(STATE_COLS)
    )
    for k, v in data_lower.items():
        if not v:
            continue
        if k in consumed:
            continue
        if k in ENRICHMENT_COL_MAP:
            target = ENRICHMENT_COL_MAP[k]
            if target == "tenure_months":
                try:
                    enrichment[target] = int(float(v))
                except (TypeError, ValueError):
                    pass
            else:
                enrichment[target] = v
        elif k in TOP_LEVEL_ENRICHED:
            if TOP_LEVEL_ENRICHED[k] == "title_qualifier":
                title_qualifier = v
            else:
                signal_tag = v
        else:
            extras[k] = v

    if extras:
        enrichment["extras"] = extras

    return {
        "name": name,
        "company": company or None,
        "title": title or None,
        "phone": phone or None,
        "email": email or None,
        "signal_tag": signal_tag or None,
        "title_qualifier": title_qualifier or None,
        "enrichment": enrichment,
        "source_file": source_file,
    }


def insert_leads_skip_duplicates(
    parsed_rows: list[LeadRow], source_file: str
) -> dict[str, Any]:
    """Insert leads in bulk, skipping any whose (name, company) already exists.

    Returns {inserted, skipped, invalid, total} — invalid = rows with no name.
    """
    client = supabase_manager.get_client()
    if not client:
        raise RuntimeError("Supabase client unavailable")

    payloads = []
    invalid = 0
    for row in parsed_rows:
        mapped = xlsx_row_to_lead_insert(row, source_file)
        if mapped is None:
            invalid += 1
            continue
        payloads.append(mapped)

    if not payloads:
        return {
            "inserted": 0, "skipped": 0, "invalid": invalid,
            "total": len(parsed_rows),
        }

    # Build the set of existing (name, company) pairs in one query, restricted
    # to names that appear in this upload to keep the response small.
    incoming_names = list({p["name"] for p in payloads})
    existing_resp = (
        client.table(LEADS_TABLE)
        .select("name, company")
        .in_("name", incoming_names)
        .execute()
    )
    existing_keys = {
        (r["name"].strip().lower(), (r.get("company") or "").strip().lower())
        for r in (existing_resp.data or [])
    }

    fresh_payloads = []
    skipped = 0
    seen_in_batch: set[tuple[str, str]] = set()
    for p in payloads:
        key = (p["name"].strip().lower(), (p["company"] or "").strip().lower())
        if key in existing_keys or key in seen_in_batch:
            skipped += 1
            continue
        seen_in_batch.add(key)
        fresh_payloads.append(p)

    inserted = 0
    if fresh_payloads:
        # Supabase has a per-request payload cap; chunk to be safe on large files.
        CHUNK = 500
        for i in range(0, len(fresh_payloads), CHUNK):
            batch = fresh_payloads[i : i + CHUNK]
            resp = client.table(LEADS_TABLE).insert(batch).execute()
            inserted += len(resp.data or batch)

    logger.info(
        "leads_writer: inserted=%d skipped=%d invalid=%d total=%d source=%s",
        inserted, skipped, invalid, len(parsed_rows), source_file,
    )
    return {
        "inserted": inserted,
        "skipped": skipped,
        "invalid": invalid,
        "total": len(parsed_rows),
    }
