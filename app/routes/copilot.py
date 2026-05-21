"""Copilot Studio / Teams bot endpoints.

POST endpoints that mirror the OpenAPI spec uploaded to Copilot Studio
(context/copilot_openapi.json):

  - POST /copilot/lookup        → find a lead by name (returns LeadRecord)
  - POST /copilot/brief         → full pre-call brief (LLM)
  - POST /copilot/respond       → real-time response suggestion (LLM)
  - POST /copilot/enrich-file   → multipart upload xlsx, enrich, return download link
"""
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from app.services.lead_finder import find_lead_by_name, row_to_lead_record
from app.services.copilot_service import generate_brief, generate_live_suggestion
from app.services.excel_parser import parse_excel, write_enriched_excel
from app.services.serpapi_enricher import enrich_leads
from app.services.storage_uploader import upload_enriched_file

logger = logging.getLogger(__name__)

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


@router.post("/enrich-file")
async def enrich_file(file: UploadFile = File(...)):
    """Enrich an Excel file uploaded directly via multipart/form-data.

    Matt drops the xlsx into the Copilot bot in Teams → bot passes the file
    content here → we run the full pipeline (parse, SerpAPI, Claude, write,
    upload to Supabase Storage) and return a public download URL.
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xls files are accepted")

    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {e}")

    # Parse the Excel
    try:
        leads = parse_excel(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Excel parse failed")
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {e}")

    if not leads:
        raise HTTPException(status_code=400, detail="No leads found in file")

    # Enrich every row (SerpAPI + Claude)
    enrichments = enrich_leads(leads)

    # Write the enriched Excel
    enriched_bytes = write_enriched_excel(leads, enrichments)

    # Upload to Supabase Storage and get a public link
    try:
        download_url = upload_enriched_file(enriched_bytes, file.filename)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Summary counts for the bot reply
    new_hires = sum(1 for e in enrichments if (e.tenure_label or "") == "NEW_HIRE")
    long_tenured = sum(1 for e in enrichments if (e.tenure_label or "") == "LONG_TENURED")
    decision_makers = sum(1 for e in enrichments if (e.title_qualifier or "") == "DECISION_MAKER")

    return {
        "status": "success",
        "rows_processed": len(enrichments),
        "decision_makers": decision_makers,
        "new_hires": new_hires,
        "long_tenured": long_tenured,
        "download_url": download_url,
        "message": (
            f"Enriched {len(enrichments)} leads "
            f"({decision_makers} decision-makers, {new_hires} new hires). "
            f"Download: {download_url}"
        ),
    }
