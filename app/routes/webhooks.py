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


@router.post("/storage-uploaded", status_code=status.HTTP_200_OK)
async def storage_uploaded(
    payload: SupabaseStorageWebhook,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Auto-populate `leads` when a new xlsx hits the uploaded-leads bucket."""
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

    client = supabase_manager.get_client()
    if not client:
        raise HTTPException(status_code=500, detail="Supabase client unavailable")

    try:
        file_bytes = client.storage.from_(UPLOADED_BUCKET).download(object_path)
    except Exception as e:
        logger.exception("Failed to download %s/%s", UPLOADED_BUCKET, object_path)
        raise HTTPException(
            status_code=500,
            detail=f"Could not download {object_path}: {e}",
        )

    try:
        parsed_rows = parse_excel(file_bytes)
    except Exception as e:
        logger.exception("Failed to parse %s", object_path)
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse {object_path}: {e}",
        )

    if not parsed_rows:
        return {
            "status": "ok", "file": object_path,
            "inserted": 0, "skipped": 0, "invalid": 0, "total": 0,
        }

    try:
        result = insert_leads_skip_duplicates(parsed_rows, source_file=object_path)
    except Exception as e:
        logger.exception("leads_writer failed for %s", object_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to insert leads from {object_path}: {e}",
        )

    # Fire enrichment after the response is sent so the webhook returns fast.
    # SerpAPI + the LLM run ~2-4s per lead, well over Supabase's 10s timeout.
    inserted_ids = result.pop("inserted_ids", [])
    if inserted_ids:
        background_tasks.add_task(enrich_leads_in_background, inserted_ids)

    return {
        "status": "ok",
        "file": object_path,
        "enrichment_queued": len(inserted_ids),
        **result,
    }


# ---------------------------------------------------------------------------
# Operational endpoints (manually or cron-triggered).
# ---------------------------------------------------------------------------


class RetryFailedRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)
    max_attempts: int = Field(default=5, ge=1, le=20)


@router.post("/retry-failed-enrichments", status_code=status.HTTP_200_OK)
async def retry_failed_enrichments(
    payload: RetryFailedRequest,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None),
) -> dict[str, Any]:
    """Re-run enrichment for leads where enrichment_status='failed'.

    Skips rows that already hit max_attempts so a permanently bad row doesn't
    burn API credits forever. Returns the number of leads queued so callers
    can paginate by re-invoking until queued=0.
    """
    expected_secret = os.getenv("WEBHOOK_SECRET")
    if not expected_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    if x_webhook_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    try:
        lead_ids = fetch_failed_lead_ids(
            limit=payload.limit, max_attempts=payload.max_attempts,
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
