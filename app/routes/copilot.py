"""Copilot Studio / Teams bot endpoints.

POST endpoints that mirror the OpenAPI spec uploaded to Copilot Studio
(context/copilot_openapi.json):

  - POST /copilot/lookup       → find a lead by name (returns LeadRecord)
  - POST /copilot/brief        → full pre-call brief (LLM)
  - POST /copilot/respond      → real-time response suggestion (LLM)
  - POST /copilot/upload-file  → stage a base64-encoded .xlsx in Supabase
"""
import base64
import binascii
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.lead_finder import find_lead_by_name, row_to_lead_record
from app.services.copilot_service import generate_brief, generate_live_suggestion
from app.services.excel_parser import parse_excel
from app.services.storage_uploader import upload_uploaded_file

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

router = APIRouter(prefix="/copilot", tags=["CoPilot"])


class LookupRequest(BaseModel):
    lead_name: str = Field(..., description="Full or partial name to look up")


class BriefRequest(BaseModel):
    lead_name: str = Field(..., description="Full name of the lead to brief Matt on")


class RespondRequest(BaseModel):
    prospect_said: str = Field(..., description="What the prospect just said")
    lead_name: str | None = Field(
        default=None, description="Name of the lead currently on the call (optional)"
    )


class UploadFileRequest(BaseModel):
    filename: str = Field(
        ...,
        description="Original filename including .xlsx/.xls extension (e.g. leads_week22.xlsx)",
        examples=["leads_week22.xlsx"],
    )
    content_base64: str = Field(
        ...,
        description="Base64-encoded contents of the .xlsx file. In a Copilot Studio Topic, bind this to the File variable's Content property.",
    )


@router.post("/lookup")
async def lookup_lead(payload: LookupRequest):
    """Find a lead by name; returns the enriched LeadRecord or 404."""
    row = find_lead_by_name(payload.lead_name)
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No lead found matching '{payload.lead_name}'",
        )
    return row_to_lead_record(row)


@router.post("/brief")
async def get_brief(payload: BriefRequest):
    """Return a structured pre-call brief for the lead."""
    row = find_lead_by_name(payload.lead_name)
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No lead found matching '{payload.lead_name}'",
        )
    lead = row_to_lead_record(row)
    return generate_brief(lead)


@router.post("/respond")
async def get_live_suggestion(payload: RespondRequest):
    """Return a 1-2 sentence response suggestion for a live call."""
    lead = None
    if payload.lead_name:
        row = find_lead_by_name(payload.lead_name)
        if row:
            lead = row_to_lead_record(row)

    return generate_live_suggestion(payload.prospect_said, lead)


@router.post("/upload-file")
async def upload_file(payload: UploadFileRequest):
    """Stage a base64-encoded .xlsx in the uploaded-leads bucket.

    Called directly from a Copilot Studio Topic as a registered tool —
    no Power Automate flow in between. The Topic captures the file via
    an Ask question (File variable) and binds:
      - filename       ← LeadsFile.Name
      - content_base64 ← LeadsFile.Content

    Validates extension + size + Excel readability before storing, so Matt
    gets immediate, specific feedback in chat instead of waiting for the
    downstream enrichment job to discover the file was bad.
    """
    filename = payload.filename or "leads.xlsx"
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx or .xls files are accepted",
        )

    # Tolerate data URI prefixes like "data:...;base64," that some clients prepend
    b64 = payload.content_base64.strip()
    if b64.startswith("data:") and "," in b64:
        b64 = b64.split(",", 1)[1]

    try:
        file_bytes = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"content_base64 is not valid base64: {e}",
        )

    size = len(file_bytes)
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size // (1024 * 1024)} MB); limit is 25 MB",
        )

    try:
        leads = parse_excel(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Excel parse failed during upload")
        raise HTTPException(
            status_code=400,
            detail=f"Could not read Excel file: {e}",
        )

    if not leads:
        raise HTTPException(status_code=400, detail="No lead rows detected in the file")

    rows_detected = len(leads)
    columns_detected = len(leads[0].headers)

    try:
        storage_path, storage_url = upload_uploaded_file(file_bytes, filename)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    message = (
        f"File uploaded successfully — {rows_detected} leads detected "
        f"in {filename}. Reply 'enrich it' to start enrichment."
    )

    return {
        "status": "success",
        "filename": filename,
        "storage_path": storage_path,
        "storage_url": storage_url,
        "rows_detected": rows_detected,
        "columns_detected": columns_detected,
        "message": message,
    }