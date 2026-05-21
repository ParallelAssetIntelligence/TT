"""Copilot Studio / Teams bot endpoints.

POST endpoints that mirror the OpenAPI spec uploaded to Copilot Studio
(context/copilot_openapi.json):

  - POST /copilot/lookup            → find a lead by name (returns LeadRecord)
  - POST /copilot/brief             → full pre-call brief (LLM)
  - POST /copilot/respond           → real-time response suggestion (LLM)
  - POST /copilot/enrich-from-url   → download a file from URL, enrich, return link
"""
import logging
import httpx
from fastapi import APIRouter, HTTPException
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


class EnrichFromUrlRequest(BaseModel):
    file_url: str = Field(..., description="Public/auth URL of the Excel file to enrich")
    filename: str | None = Field(
        default="leads.xlsx",
        description="Original filename (used for the saved enriched file)",
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


@router.post("/enrich-from-url")
async def enrich_from_url(payload: EnrichFromUrlRequest):
    """Download an Excel file from a URL, enrich it, return a download link.

    Called by a Power Automate flow after the flow has uploaded Matt's file
    to Supabase Storage (uploaded-leads bucket). We download from that URL,
    run the full pipeline, and return a Supabase Storage link to the
    enriched file the bot can hand back to Matt.
    """
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(payload.file_url)
        if r.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Could not download file from URL (HTTP {r.status_code})",
            )
        file_bytes = r.content
    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {e}")

    try:
        leads = parse_excel(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Excel parse failed")
        raise HTTPException(status_code=400, detail=f"Invalid Excel file: {e}")

    if not leads:
        raise HTTPException(status_code=400, detail="No leads found in file")

    enrichments = enrich_leads(leads)
    enriched_bytes = write_enriched_excel(leads, enrichments)

    try:
        download_url = upload_enriched_file(enriched_bytes, payload.filename or "leads.xlsx")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

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