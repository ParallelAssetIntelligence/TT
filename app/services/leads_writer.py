"""Insert parsed Excel rows into the Supabase `leads` table + run SerpAPI enrichment.

Used by /webhooks/storage-uploaded when a new xlsx lands in the uploaded-leads
bucket. Maps the loose Excel column conventions (Name vs First+Last, Company vs
Account, etc.) onto the leads schema, then skips any rows whose (name, company)
pair already exists. After insert, the webhook schedules
enrich_leads_in_background() so SerpAPI + the LLM intelligence layer fill in
LinkedIn, tenure, opener, etc. without blocking the webhook response.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any

from app.databaseconnection import supabase_manager
from app.models.lead import LeadRow

logger = logging.getLogger(__name__)

LEADS_TABLE = "leads"
ENRICH_DELAY_SECONDS = 1.0  # rate-limit gap between SerpAPI calls

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
            "total": len(parsed_rows), "inserted_ids": [],
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
    inserted_ids: list[int] = []
    if fresh_payloads:
        # Supabase has a per-request payload cap; chunk to be safe on large files.
        CHUNK = 500
        for i in range(0, len(fresh_payloads), CHUNK):
            batch = fresh_payloads[i : i + CHUNK]
            resp = client.table(LEADS_TABLE).insert(batch).execute()
            returned = resp.data or []
            inserted += len(returned) or len(batch)
            inserted_ids.extend(
                r["id"] for r in returned if isinstance(r, dict) and "id" in r
            )

    logger.info(
        "leads_writer: inserted=%d skipped=%d invalid=%d total=%d source=%s",
        inserted, skipped, invalid, len(parsed_rows), source_file,
    )
    return {
        "inserted": inserted,
        "skipped": skipped,
        "invalid": invalid,
        "total": len(parsed_rows),
        "inserted_ids": inserted_ids,
    }


# ---------------------------------------------------------------------------
# SerpAPI + LLM enrichment for inserted leads.
# ---------------------------------------------------------------------------


def _row_to_leadrow(row: dict[str, Any]) -> LeadRow:
    """Wrap a DB row in a LeadRow so the SerpAPI enricher can query it.

    Only the basic contact + location fields are fed into the search query;
    pre-existing enrichment is intentionally excluded so we don't echo prior
    enrichment results back into the new SerpAPI search.
    """
    enrichment = row.get("enrichment") or {}
    headers = ["Name", "Company", "Title", "Phone", "Email", "City", "State"]
    data = {
        "Name": row.get("name") or "",
        "Company": row.get("company") or "",
        "Title": row.get("title") or "",
        "Phone": row.get("phone") or "",
        "Email": row.get("email") or "",
        "City": enrichment.get("city") or "",
        "State": enrichment.get("state") or "",
    }
    return LeadRow(headers=headers, data=data)


def _enrich_single_lead(lead_id: int) -> bool:
    """Enrich one lead by id. Returns True on success, False on any failure."""
    # Local import keeps the route module light + avoids loading SerpAPI / LLM
    # clients until enrichment actually runs.
    from app.services.serpapi_enricher import enrich_lead

    client = supabase_manager.get_client()
    if not client:
        logger.error("enrich_lead %d: Supabase client unavailable", lead_id)
        return False

    fetched = (
        client.table(LEADS_TABLE).select("*").eq("id", lead_id).limit(1).execute()
    )
    if not fetched.data:
        logger.warning("enrich_lead %d: row not found", lead_id)
        return False

    row = fetched.data[0]
    try:
        enriched = enrich_lead(_row_to_leadrow(row))
    except Exception:
        logger.exception("enrich_lead %d: enricher raised", lead_id)
        return False

    # Merge into the existing enrichment jsonb so any extras stay intact.
    existing = row.get("enrichment") or {}
    merged = {
        **existing,
        "website": enriched.website or existing.get("website") or "",
        "linkedin_url": enriched.linkedin or existing.get("linkedin_url") or "",
        "linkedin_headline": enriched.linkedin_headline or existing.get("linkedin_headline") or "",
        "linkedin_summary": enriched.linkedin_summary or existing.get("linkedin_summary") or "",
        "linkedin_company_description":
            enriched.linkedin_company_description or existing.get("linkedin_company_description") or "",
        "location": enriched.location or existing.get("location") or "",
        "description": enriched.description or existing.get("description") or "",
        "tenure_months": enriched.tenure_months
            if enriched.tenure_months is not None else existing.get("tenure_months"),
        "tenure_label": enriched.tenure_label or existing.get("tenure_label") or "",
        "prior_company_1": enriched.prior_company_1 or existing.get("prior_company_1") or "",
        "prior_company_2": enriched.prior_company_2 or existing.get("prior_company_2") or "",
        "script_used": enriched.script_used or existing.get("script_used") or "",
        "personalized_opener":
            enriched.personalized_opener or existing.get("personalized_opener") or "",
    }

    update_payload: dict[str, Any] = {
        "enrichment": merged,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Only overwrite the top-level qualifier/tag if the enricher actually
    # produced a value — keep whatever was on the row otherwise.
    if enriched.title_qualifier:
        update_payload["title_qualifier"] = enriched.title_qualifier
    if enriched.signal_tag:
        update_payload["signal_tag"] = enriched.signal_tag

    try:
        client.table(LEADS_TABLE).update(update_payload).eq("id", lead_id).execute()
    except Exception:
        logger.exception("enrich_lead %d: DB update failed", lead_id)
        return False

    return True


def enrich_leads_in_background(lead_ids: list[int]) -> None:
    """Run SerpAPI + LLM enrichment for each lead id; updates leads in place.

    Designed to be scheduled via FastAPI BackgroundTasks so the webhook can
    return immediately. Continues past individual failures and sleeps between
    SerpAPI calls to stay under rate limits.
    """
    if not lead_ids:
        return

    logger.info("Background enrichment starting for %d leads", len(lead_ids))
    succeeded = 0
    failed = 0
    for i, lead_id in enumerate(lead_ids):
        if _enrich_single_lead(lead_id):
            succeeded += 1
        else:
            failed += 1
        if i < len(lead_ids) - 1:
            time.sleep(ENRICH_DELAY_SECONDS)

    logger.info(
        "Background enrichment finished: succeeded=%d failed=%d total=%d",
        succeeded, failed, len(lead_ids),
    )
