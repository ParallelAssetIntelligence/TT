"""Inbound webhooks (currently: Supabase Storage upload events).

Configure in Supabase:
  Database → Webhooks → Create webhook
    Name:       leads_storage_uploaded
    Table:      storage.objects
    Events:     INSERT
    Method:     POST
    URL:        https://<your-railway-url>/webhooks/storage-uploaded
    HTTP Headers:
      x-webhook-secret: <value of WEBHOOK_SECRET env var>

The endpoint filters for the `uploaded-leads` bucket + .xlsx/.xls files,
downloads the new object, parses it, and inserts any new (name, company)
pairs into the `leads` table. Duplicates are skipped.
"""
import logging
import os
from typing import Any

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.databaseconnection import supabase_manager
from app.services.excel_parser import parse_excel
from app.services.leads_writer import (
    enrich_leads_in_background,
    fetch_failed_lead_ids,
    insert_leads_skip_duplicates,
)
from app.services.storage_uploader import UPLOADED_BUCKET

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class StorageObjectRecord(BaseModel):
    bucket_id: str | None = None
    name: str | None = None
    # other fields (id, owner, metadata, ...) are ignored


class SupabaseStorageWebhook(BaseModel):
    # Supabase sends a field literally named "schema", which clashes with
    # BaseModel.schema(); alias it to schema_.
    model_config = ConfigDict(populate_by_name=True)

    type: str | None = None
    table: str | None = None
    schema_: str | None = Field(default=None, alias="schema")
    record: StorageObjectRecord | None = None


def _process_uploaded_file(bucket: str, object_path: str) -> None:
    """Heavy lifting that used to run inside the webhook handler.

    Moved to a background task so the webhook itself returns in ~50ms,
    eliminating the 10-second Supabase timeout cliff for big files.

    Resume-on-retry: if Supabase retries this webhook because an earlier
    attempt timed out, the dedupe_key unique index makes the insert step
    idempotent (already-inserted rows are skipped). After insert, we
    also pick up ANY pending rows tagged with this source_file — that
    way, leftover rows whose enrichment never got scheduled in a prior
    attempt are caught and enriched this time around.
    """
    client = supabase_manager.get_client()
    if not client:
        logger.error("storage-uploaded background: Supabase client unavailable")
        return

    try:
        file_bytes = client.storage.from_(bucket).download(object_path)
    except Exception:
        logger.exception("background: failed to download %s/%s", bucket, object_path)
        return

    try:
        parsed_rows = parse_excel(file_bytes)
    except Exception:
        logger.exception("background: failed to parse %s", object_path)
        return

    if not parsed_rows:
        logger.info("background: %s has no rows; nothing to do", object_path)
        return

    try:
        result = insert_leads_skip_duplicates(parsed_rows, source_file=object_path)
    except Exception:
        logger.exception("background: leads_writer failed for %s", object_path)
        return

    freshly_inserted = result.get("inserted_ids") or []

    # Resume: pull every still-pending row for this file (could include
    # leftovers from a prior webhook attempt whose enrichment never
    # got scheduled because the handler timed out).
    leftover_ids: list[int] = []
    try:
        leftover_resp = (
            client.table("leads")
            .select("id")
            .eq("source_file", object_path)
            .eq("enrichment_status", "pending")
            .execute()
        )
        leftover_ids = [
            r["id"] for r in (leftover_resp.data or []) if "id" in r
        ]
    except Exception:
        logger.exception(
            "background: leftover-pending lookup failed for %s", object_path
        )

    all_ids = sorted(set(freshly_inserted) | set(leftover_ids))
    if not all_ids:
        logger.info(
            "background: %s — nothing to enrich (inserted=%d leftover=%d)",
            object_path, len(freshly_inserted), len(leftover_ids),
        )
        skipped = result.get("skipped", 0)
        total = result.get("total", len(parsed_rows))
        if skipped > 0:
            # Look up the original source_file from existing DB rows so the
            # download URL points to the right file (not the new timestamped name).
            original_source = object_path
            dedupe_keys = result.get("dedupe_keys") or []
            if dedupe_keys and client:
                try:
                    resp = (
                        client.table("leads")
                        .select("source_file")
                        .in_("dedupe_key", dedupe_keys[:10])
                        .limit(1)
                        .execute()
                    )
                    if resp.data and resp.data[0].get("source_file"):
                        original_source = resp.data[0]["source_file"]
                except Exception:
                    logger.exception("background: failed to look up original source_file")
            _notify_all_skipped(original_source, total, skipped)
        return

    logger.info(
        "background: %s — enriching %d leads (fresh=%d resume=%d)",
        object_path, len(all_ids), len(freshly_inserted),
        len(set(leftover_ids) - set(freshly_inserted)),
    )
    enrich_leads_in_background(all_ids)


def _notify_all_skipped(filename: str, total_rows: int, skipped: int) -> None:
    """Fire Teams + email when every row in an upload was a duplicate."""
    try:
        from app.services.teams_notifier import (
            build_download_url,
            send_upload_skipped as teams_skipped,
        )
        from app.services.email_notifier import send_upload_skipped as email_skipped

        download_url = build_download_url(filename)
        teams_skipped(filename, total_rows, skipped, file_url=download_url)
        email_skipped(filename, total_rows, skipped, file_url=download_url)
    except Exception:
        logger.exception("Skipped-upload notification failed (continuing anyway)")


@router.post("/storage-uploaded", status_code=status.HTTP_200_OK)
async def storage_uploaded(
    payload: SupabaseStorageWebhook,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Acknowledge that a new xlsx hit the uploaded-leads bucket.

    All the heavy lifting (download, parse, insert, enrich) runs in a
    BackgroundTask AFTER the response is sent, so this handler returns
    in ~50ms regardless of file size. That sidesteps Supabase's hard
    10-second webhook timeout, which is impossible to satisfy
    synchronously for >1k row files.
    """
    expected_secret = os.getenv("WEBHOOK_SECRET")
    if not expected_secret:
        logger.error("WEBHOOK_SECRET env var not set — refusing webhook")
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    record = payload.record
    if not record or not record.bucket_id or not record.name:
        return {"status": "ignored", "reason": "payload missing bucket_id/name"}

    if record.bucket_id != UPLOADED_BUCKET:
        return {
            "status": "ignored",
            "reason": f"bucket {record.bucket_id} is not {UPLOADED_BUCKET}",
        }

    object_path = record.name
    if not object_path.lower().endswith((".xlsx", ".xls")):
        return {
            "status": "ignored",
            "reason": f"{object_path} is not an Excel file",
        }

    background_tasks.add_task(_process_uploaded_file, UPLOADED_BUCKET, object_path)

    return {"status": "accepted", "file": object_path}


# ---------------------------------------------------------------------------
# Operational endpoints (manually or cron-triggered).
# ---------------------------------------------------------------------------


class RetryFailedRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    max_attempts: int = Field(default=5, ge=1, le=20)
    idle_minutes_for_stuck: int = Field(
        default=2,
        ge=1,
        le=120,
        description=(
            "How many minutes of system-wide enrichment inactivity before "
            "pending rows are considered stuck. During a healthy batch, "
            "MAX(enriched_at) advances every few seconds — once it stops "
            "for this long, the worker is dead and pending rows are rescued."
        ),
    )


@router.post("/retry-failed-enrichments", status_code=status.HTTP_200_OK)
async def retry_failed_enrichments(
    payload: RetryFailedRequest,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Re-run enrichment for failed rows + stuck-pending rows.

    A row counts as "stuck pending" when the system as a whole hasn't
    finished an enrichment in `idle_minutes_for_stuck` minutes — i.e. the
    worker has clearly stopped working. Returns the number of leads
    queued so callers can paginate by re-invoking until queued=0.
    """
    expected_secret = os.getenv("WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        lead_ids = fetch_failed_lead_ids(
            limit=payload.limit,
            max_attempts=payload.max_attempts,
            idle_minutes_for_stuck=payload.idle_minutes_for_stuck,
        )
    except Exception as e:
        logger.exception("retry: failed to fetch failed lead ids")
        raise HTTPException(status_code=500, detail=str(e))

    if lead_ids:
        background_tasks.add_task(enrich_leads_in_background, lead_ids)
    return {"status": "ok", "queued": len(lead_ids), "lead_ids": lead_ids[:25]}


class CleanupBucketRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=3650)
    dry_run: bool = Field(default=False)


@router.post("/cleanup-bucket", status_code=status.HTTP_200_OK)
async def cleanup_bucket(
    payload: CleanupBucketRequest,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Delete files older than `days` from the uploaded-leads bucket.

    Intended to be called on a schedule (Supabase pg_cron, Railway cron, or
    any external scheduler). Pass dry_run=true to preview what would be
    deleted without actually removing anything.
    """
    expected_secret = os.getenv("WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    client = supabase_manager.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="Supabase client unavailable")

    cutoff = datetime.now(timezone.utc) - timedelta(days=payload.days)
    try:
        files = client.storage.from_(UPLOADED_BUCKET).list()
    except Exception as e:
        logger.exception("cleanup-bucket: list failed")
        raise HTTPException(status_code=500, detail=f"Could not list bucket: {e}")

    stale_paths: list[str] = []
    for f in files or []:
        # Storage list entries have shape: {name, id, created_at, ...}
        name = f.get("name") if isinstance(f, dict) else None
        created_at_raw = f.get("created_at") if isinstance(f, dict) else None
        if not name or not created_at_raw:
            continue
        try:
            # Supabase returns ISO 8601, sometimes with a 'Z' suffix.
            created_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if created_at < cutoff:
            stale_paths.append(name)

    if payload.dry_run or not stale_paths:
        return {
            "status": "ok",
            "would_delete": len(stale_paths),
            "deleted": 0,
            "cutoff": cutoff.isoformat(),
            "sample": stale_paths[:10],
        }

    try:
        # supabase-py's storage.remove accepts a list of paths.
        client.storage.from_(UPLOADED_BUCKET).remove(stale_paths)
    except Exception as e:
        logger.exception("cleanup-bucket: remove failed")
        raise HTTPException(status_code=500, detail=f"Could not delete files: {e}")

    return {
        "status": "ok",
        "deleted": len(stale_paths),
        "cutoff": cutoff.isoformat(),
        "sample": stale_paths[:10],
    }
