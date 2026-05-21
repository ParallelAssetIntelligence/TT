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

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.databaseconnection import supabase_manager
from app.services.excel_parser import parse_excel
from app.services.leads_writer import insert_leads_skip_duplicates
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

    return {"status": "ok", "file": object_path, **result}
