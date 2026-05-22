"""Insert parsed Excel rows into the Supabase `leads` table + run SerpAPI enrichment.

Used by /webhooks/storage-uploaded when a new xlsx lands in the uploaded-leads
bucket. Maps loose Excel column conventions (Name vs First+Last, Company vs
Account) onto the leads schema, then upserts with a canonical dedupe_key so
duplicates are caught at the DB layer (insensitive to whitespace, casing,
and common company suffixes like Inc / LLC / Corp).

After insert, the webhook schedules enrich_leads_in_background() which runs
SerpAPI + the LLM intelligence layer concurrently across multiple threads,
recording per-row status (`pending` / `done` / `failed`) so the retry endpoint
can re-attempt failed rows.
"""
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from app.databaseconnection import supabase_manager
from app.models.lead import LeadRow

logger = logging.getLogger(__name__)

LEADS_TABLE = "leads"

# Parallel SerpAPI + LLM calls. 5 is a safe default — SerpAPI's free tier
# allows ~100 req/min, and each enrichment costs 1 SerpAPI + 1 OpenRouter call.
ENRICH_CONCURRENCY = int(os.getenv("ENRICH_CONCURRENCY", "5"))

# Inline retry for transient enricher errors (network blips, rate limits, brief
# LLM outages). Each retry sleeps with exponential backoff: 1s, 2s, 4s. Only
# applies inside a single enrichment attempt — the leads.enrichment_attempts
# counter still increments by 1 per call to _enrich_single_lead.
INLINE_RETRY_ATTEMPTS = int(os.getenv("ENRICH_INLINE_RETRIES", "3"))
INLINE_RETRY_BACKOFF_BASE_SECONDS = 1.0

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

# Optional "extras" we now harvest from the uploaded file (when present) so
# SerpAPI gets a better search query and we skip API calls for data the client
# already gave us.
LINKEDIN_COLS = [
    "linkedin", "linkedin url", "linkedin_url", "li", "li_url", "linkedin profile",
]
INDUSTRY_COLS = ["industry", "industries", "vertical", "sector"]
DEPARTMENT_COLS = ["department", "dept", "function", "team"]
WEBSITE_COLS = ["website", "company website", "url", "domain", "company url"]

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

# Common legal-entity suffixes we strip when normalizing company names so
# "ABC Hospital" and "ABC Hospital, Inc." dedupe to the same key.
_COMPANY_SUFFIX_RE = re.compile(
    r"[,.\s]+(inc|llc|ltd|corp|corporation|company|co|gmbh|sa|plc|pty|holdings)\.?\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Normalization helpers (mirrored by the SQL backfill in leads_table_v2_migration.sql)
# ---------------------------------------------------------------------------


def _normalize_phone(phone: str) -> str:
    """Return the last 10 digits of a phone number, or '' if too few digits."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else ""


def _normalize_company(company: str) -> str:
    """Lowercase, strip Inc/LLC/Corp suffixes, collapse whitespace."""
    c = (company or "").strip().lower()
    # Strip suffixes repeatedly in case of stacked ones ("Acme Corp Inc")
    while True:
        new = _COMPANY_SUFFIX_RE.sub("", c).strip()
        if new == c:
            break
        c = new
    return re.sub(r"\s+", " ", c)


def _compute_dedupe_key(payload: dict[str, Any]) -> str:
    """Canonical identity key. Phone is preferred when present."""
    phone = _normalize_phone(payload.get("phone", "") or "")
    if phone:
        return f"phone:{phone}"
    name = (payload.get("name") or "").strip().lower()
    company = _normalize_company(payload.get("company") or "")
    return f"nc:{name}|{company}"


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

    # Pre-populate enrichment from optional columns the upload already
    # contains. These also feed into the SerpAPI search query so we get
    # better results than searching by name+company alone.
    industry = _lookup(data_lower, INDUSTRY_COLS)
    if industry:
        enrichment["industry"] = industry
    department = _lookup(data_lower, DEPARTMENT_COLS)
    if department:
        enrichment["department"] = department
    linkedin_from_file = _lookup(data_lower, LINKEDIN_COLS)
    if linkedin_from_file:
        enrichment["linkedin_url"] = linkedin_from_file
    website_from_file = _lookup(data_lower, WEBSITE_COLS)
    if website_from_file:
        enrichment["website"] = website_from_file

    title_qualifier = ""
    signal_tag = ""

    # Pull Enriched_* columns into the enrichment jsonb and promote the
    # qualifier/tag to their top-level slots. The full original row is
    # preserved verbatim in raw_excel_row below, so we no longer need an
    # `extras` catch-all.
    for k, v in data_lower.items():
        if not v:
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

    # Verbatim copy of the spreadsheet row (header → cell value). Lets
    # /leads/download regenerate an xlsx that mirrors the original file.
    raw_excel_row = {
        k: v for k, v in row.data.items() if k and v != ""
    }

    # Only skip enrichment if the upload already includes a personalized opener
    # (i.e. came from a previously-enriched export). A bare LinkedIn URL from
    # ZoomInfo etc. is useful context but still needs the LLM intelligence
    # layer to fill in tenure, signal, opener.
    has_existing_enrichment = bool(enrichment.get("personalized_opener"))

    payload: dict[str, Any] = {
        "name": name,
        "company": company or None,
        "title": title or None,
        "phone": phone or None,
        "email": email or None,
        "signal_tag": signal_tag or None,
        "title_qualifier": title_qualifier or None,
        "enrichment": enrichment,
        "raw_excel_row": raw_excel_row,
        "source_file": source_file,
        "enrichment_status": "done" if has_existing_enrichment else "pending",
    }
    if has_existing_enrichment:
        payload["enriched_at"] = _now_iso()

    payload["dedupe_key"] = _compute_dedupe_key(payload)
    return payload


def insert_leads_skip_duplicates(
    parsed_rows: list[LeadRow], source_file: str
) -> dict[str, Any]:
    """Insert leads, letting the DB's unique(dedupe_key) index reject duplicates.

    Returns {inserted, skipped, invalid, total, inserted_ids}.
    """
    client = supabase_manager.get_client()
    if not client:
        raise RuntimeError("Supabase client unavailable")

    payloads: list[dict[str, Any]] = []
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

    # Collapse intra-batch duplicates first — multiple rows in the same file
    # mapping to the same dedupe_key would otherwise cause an upsert error.
    deduped: dict[str, dict[str, Any]] = {}
    intra_skipped = 0
    for p in payloads:
        key = p["dedupe_key"]
        if key in deduped:
            intra_skipped += 1
            continue
        deduped[key] = p
    fresh_payloads = list(deduped.values())

    inserted = 0
    inserted_ids: list[int] = []
    if fresh_payloads:
        CHUNK = 500
        for i in range(0, len(fresh_payloads), CHUNK):
            batch = fresh_payloads[i : i + CHUNK]
            # ignore_duplicates=True turns conflicts on dedupe_key into a no-op
            # instead of raising. Returns only the genuinely inserted rows.
            resp = (
                client.table(LEADS_TABLE)
                .upsert(batch, on_conflict="dedupe_key", ignore_duplicates=True)
                .execute()
            )
            returned = resp.data or []
            inserted += len(returned)
            inserted_ids.extend(
                r["id"] for r in returned if isinstance(r, dict) and "id" in r
            )

    skipped = (len(payloads) - inserted)  # intra-batch + cross-batch combined
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
# SerpAPI + LLM enrichment (parallelized via thread pool, status-tracked).
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_leadrow(row: dict[str, Any]) -> LeadRow:
    """Wrap a DB row in a LeadRow so the SerpAPI enricher can query it.

    Includes optional context columns (industry, department, LinkedIn URL,
    website) when the upload provided them — this tightens SerpAPI's match
    on ambiguous names and lets the LLM ground its analysis on the right
    company. Empty fields are omitted from the search query by
    LeadRow.search_text().
    """
    enrichment = row.get("enrichment") or {}
    data: dict[str, str] = {
        "Name": row.get("name") or "",
        "Company": row.get("company") or "",
        "Title": row.get("title") or "",
        "Phone": row.get("phone") or "",
        "Email": row.get("email") or "",
        "City": enrichment.get("city") or "",
        "State": enrichment.get("state") or "",
    }
    # Optional extras — only add if non-empty (search_text already skips
    # empties, but this keeps the headers list tidy).
    for label, key in (
        ("Industry", "industry"),
        ("Department", "department"),
        ("LinkedIn", "linkedin_url"),
        ("Website", "website"),
    ):
        value = enrichment.get(key) or ""
        if value:
            data[label] = value
    return LeadRow(headers=list(data.keys()), data=data)


def _mark_failed(client, lead_id: int, error: str, attempts: int) -> None:
    try:
        client.table(LEADS_TABLE).update({
            "enrichment_status": "failed",
            "enrichment_error": (error or "")[:500],
            "enrichment_attempts": attempts + 1,
            "updated_at": _now_iso(),
        }).eq("id", lead_id).execute()
    except Exception:
        logger.exception("Failed to mark lead %d as failed", lead_id)


def _enrich_single_lead(lead_id: int) -> bool:
    """Enrich one lead by id. Returns True on success, False on any failure.

    On failure, the row is marked enrichment_status='failed' with the error
    message and attempts counter incremented — so the retry endpoint can pick
    it up.
    """
    # Local import keeps the route module light and avoids loading SerpAPI /
    # OpenRouter clients until enrichment actually runs.
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
    current_attempts = int(row.get("enrichment_attempts") or 0)
    leadrow = _row_to_leadrow(row)

    # Inline retry for transient errors. Most SerpAPI errors are swallowed
    # inside enrich_lead() (returns blank EnrichedData), but the LLM call can
    # raise on rate limits or 5xx — those benefit from a quick retry.
    enriched = None
    last_error: str | None = None
    for attempt_idx in range(INLINE_RETRY_ATTEMPTS):
        try:
            enriched = enrich_lead(leadrow)
            break
        except Exception as e:
            last_error = str(e)[:300] or e.__class__.__name__
            remaining = INLINE_RETRY_ATTEMPTS - attempt_idx - 1
            if remaining > 0:
                wait = INLINE_RETRY_BACKOFF_BASE_SECONDS * (2 ** attempt_idx)
                logger.warning(
                    "enrich_lead %d: attempt %d/%d failed (%s) — retrying in %ds",
                    lead_id, attempt_idx + 1, INLINE_RETRY_ATTEMPTS, last_error, wait,
                )
                time.sleep(wait)
            else:
                logger.error(
                    "enrich_lead %d: all %d inline retries exhausted (%s)",
                    lead_id, INLINE_RETRY_ATTEMPTS, last_error,
                )

    if enriched is None:
        _mark_failed(client, lead_id, last_error or "unknown error", current_attempts)
        return False

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
        "updated_at": _now_iso(),
        "enriched_at": _now_iso(),
        "enrichment_status": "done",
        "enrichment_error": None,
        "enrichment_attempts": current_attempts + 1,
    }
    if enriched.title_qualifier:
        update_payload["title_qualifier"] = enriched.title_qualifier
    if enriched.signal_tag:
        update_payload["signal_tag"] = enriched.signal_tag

    try:
        client.table(LEADS_TABLE).update(update_payload).eq("id", lead_id).execute()
    except Exception as e:
        logger.exception("enrich_lead %d: DB update failed", lead_id)
        _mark_failed(client, lead_id, str(e), current_attempts)
        return False

    return True


def enrich_leads_in_background(lead_ids: list[int]) -> None:
    """Enrich a batch of leads concurrently via ThreadPoolExecutor.

    Designed to be scheduled via FastAPI BackgroundTasks. Each task isolates
    its own failure and writes its status to the DB, so a single bad row
    can't poison the batch. Posts a single Teams notification after the
    whole batch finishes.
    """
    if not lead_ids:
        return

    logger.info(
        "Background enrichment starting: %d leads, %d concurrent workers",
        len(lead_ids), ENRICH_CONCURRENCY,
    )
    succeeded = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=ENRICH_CONCURRENCY) as executor:
        for ok in executor.map(_enrich_single_lead, lead_ids):
            if ok:
                succeeded += 1
            else:
                failed += 1

    logger.info(
        "Background enrichment finished: succeeded=%d failed=%d total=%d",
        succeeded, failed, len(lead_ids),
    )

    _notify_batch_complete(lead_ids, succeeded=succeeded, failed=failed)


def _notify_batch_complete(lead_ids: list[int], succeeded: int, failed: int) -> None:
    """Send one Teams card summarizing the batch. Best-effort: never raises."""
    try:
        from app.services.teams_notifier import (
            build_download_url,
            send_enrichment_complete,
        )

        client = supabase_manager.get_client()
        if not client:
            return

        # Pull the source_file and tenure_label tally for the rows we just touched.
        resp = (
            client.table(LEADS_TABLE)
            .select("source_file, enrichment")
            .in_("id", lead_ids)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return

        source_file = next(
            (r["source_file"] for r in rows if r.get("source_file")),
            "leads.xlsx",
        )
        new_hires = sum(
            1 for r in rows
            if (r.get("enrichment") or {}).get("tenure_label") == "NEW_HIRE"
        )
        long_tenured = sum(
            1 for r in rows
            if (r.get("enrichment") or {}).get("tenure_label") == "LONG_TENURED"
        )

        send_enrichment_complete(
            filename=source_file,
            rows_processed=succeeded,
            rows_failed=failed,
            new_hires=new_hires,
            long_tenured=long_tenured,
            file_url=build_download_url(source_file),
        )
    except Exception:
        # Notifications are advisory — never let a Teams hiccup break the pipeline.
        logger.exception("Teams notification failed (continuing anyway)")


def fetch_failed_lead_ids(
    limit: int = 100,
    max_attempts: int = 5,
    idle_minutes_for_stuck: int = 3,
) -> list[int]:
    """Return ids of leads that need (re-)enrichment.

    Picks up two kinds of rows:
      1. enrichment_status='failed' with attempts < max_attempts — same as
         before: retry rows the enricher explicitly marked failed.
      2. enrichment_status='pending', but ONLY when the system as a whole
         has been idle for >= idle_minutes_for_stuck. During a healthy
         batch the worker is finishing enrichments every few seconds, so
         MAX(enriched_at) keeps moving forward. The moment that timestamp
         stops advancing for more than the idle window, the worker is
         dead and every pending row is stuck.

      Fallback for the never-enriched-anything case (system cold-start or
      legacy data): treat a pending row as stuck if its own created_at
      is older than the idle window.
    """
    client = supabase_manager.get_client()
    if not client:
        raise RuntimeError("Supabase client unavailable")

    # 1. Failed rows still under the retry cap.
    failed_resp = (
        client.table(LEADS_TABLE)
        .select("id")
        .eq("enrichment_status", "failed")
        .lt("enrichment_attempts", max_attempts)
        .order("id")
        .limit(limit)
        .execute()
    )
    ids: list[int] = [r["id"] for r in (failed_resp.data or []) if "id" in r]
    if len(ids) >= limit:
        return ids

    # 2. Activity check — how long ago was the LAST enrichment system-wide?
    activity_resp = (
        client.table(LEADS_TABLE)
        .select("enriched_at")
        .not_.is_("enriched_at", "null")
        .order("enriched_at", desc=True)
        .limit(1)
        .execute()
    )
    last_activity: datetime | None = None
    if activity_resp.data and activity_resp.data[0].get("enriched_at"):
        try:
            last_activity = datetime.fromisoformat(
                activity_resp.data[0]["enriched_at"].replace("Z", "+00:00")
            )
        except ValueError:
            last_activity = None

    idle_cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=idle_minutes_for_stuck
    )

    # System is "idle" if either (a) we have never enriched anything OR
    # (b) the most recent enrichment is older than the idle window.
    system_idle = last_activity is None or last_activity < idle_cutoff

    if system_idle:
        remaining = limit - len(ids)
        pending_query = (
            client.table(LEADS_TABLE)
            .select("id")
            .eq("enrichment_status", "pending")
        )
        # In the cold-start case (no enrichment ever) we still want to
        # avoid grabbing rows inserted seconds ago that a live worker
        # might be processing. Bound by the row's own age.
        if last_activity is None:
            cold_cutoff = (
                datetime.now(timezone.utc)
                - timedelta(minutes=idle_minutes_for_stuck)
            ).isoformat()
            pending_query = pending_query.lt("created_at", cold_cutoff)

        pending_resp = (
            pending_query.order("id").limit(remaining).execute()
        )
        ids.extend(
            r["id"] for r in (pending_resp.data or []) if "id" in r
        )

    return ids
