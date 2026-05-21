"""Copilot Studio / Teams bot endpoints.

POST endpoints that mirror the OpenAPI spec uploaded to Copilot Studio
(context/copilot_openapi.json):

  - POST /copilot/lookup           → find a lead by name (returns LeadRecord)
  - POST /copilot/brief            → full pre-call brief (LLM)
  - POST /copilot/respond          → real-time response suggestion (LLM)
  - POST /copilot/upload-file      → stage a base64-encoded .xlsx in Supabase
  - POST /copilot/upload-from-url  → download a public .xlsx URL into Supabase
"""
import base64
import binascii
import ipaddress
import logging
import os
import re
import socket
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.lead_finder import find_lead_by_name, row_to_lead_record
from app.services.copilot_service import generate_brief, generate_live_suggestion
from app.services.excel_parser import parse_excel
from app.services.storage_uploader import upload_uploaded_file

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
DOWNLOAD_TIMEOUT_SECONDS = 30.0

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


class UploadFromUrlRequest(BaseModel):
    url: str = Field(
        ...,
        description=(
            "Public HTTPS URL to a .xlsx/.xls file. Google Drive, Dropbox, and "
            "OneDrive share links are auto-converted to direct downloads."
        ),
        examples=["https://drive.google.com/file/d/1aBcDeF/view?usp=sharing"],
    )
    filename: str | None = Field(
        default=None,
        description=(
            "Optional override for the stored filename. If omitted, derived from "
            "Content-Disposition header or the URL path."
        ),
        examples=["leads_week22.xlsx"],
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


def _stage_xlsx_bytes(file_bytes: bytes, filename: str) -> dict:
    """Shared post-download validation + Supabase upload, returning the standard response.

    Used by both /upload-file (base64 body) and /upload-from-url (downloaded bytes).
    """
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


def _normalize_share_url(url: str) -> str:
    """Convert common share-page URLs to direct-download URLs."""
    # Google Sheets: docs.google.com/spreadsheets/d/{id}/edit → /export?format=xlsx
    m = re.match(r"https?://docs\.google\.com/spreadsheets/d/([^/]+)", url)
    if m:
        return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx"
    # Google Drive file view: drive.google.com/file/d/{id}/view → uc?export=download
    m = re.match(r"https?://drive\.google\.com/file/d/([^/]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    # Google Drive open?id=: drive.google.com/open?id={id} → uc?export=download
    m = re.match(r"https?://drive\.google\.com/open\?id=([^&#]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    # Dropbox: force dl=1 so the server returns the file instead of an HTML preview
    if "dropbox.com" in url:
        parsed = urlparse(url)
        q = parse_qs(parsed.query, keep_blank_values=True)
        q["dl"] = ["1"]
        return urlunparse(parsed._replace(query=urlencode(q, doseq=True)))
    # SharePoint (incl. OneDrive for Business) and OneDrive personal: append download=1.
    # Covers tenant.sharepoint.com share links (:x:/g/, :b:/g/, etc.), 1drv.ms short
    # links, and onedrive.live.com personal links.
    if (
        "sharepoint.com" in url
        or "1drv.ms" in url
        or "onedrive.live.com" in url
    ) and "download=1" not in url:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}download=1"
    return url


def _validate_safe_url(url: str) -> None:
    """SSRF guard: require https and reject hosts that resolve to non-public IPs."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise HTTPException(status_code=400, detail="URL must use https://")
    host = parsed.hostname
    if not host:
        raise HTTPException(status_code=400, detail="URL is missing a hostname")
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as e:
        raise HTTPException(status_code=400, detail=f"Could not resolve host '{host}': {e}")
    for addr in addrs:
        ip = ipaddress.ip_address(addr)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(
                status_code=400,
                detail="URL resolves to a non-public address and was blocked",
            )


def _filename_from_response(resp: httpx.Response, fallback_url: str) -> str:
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    name = os.path.basename(urlparse(fallback_url).path)
    return name or "leads.xlsx"


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

    return _stage_xlsx_bytes(file_bytes, filename)


@router.post("/upload-from-url")
async def upload_from_url(payload: UploadFromUrlRequest):
    """Download a public .xlsx URL and stage it in the uploaded-leads bucket.

    Lets Matt paste a share link (Google Drive, Dropbox, OneDrive, or any direct
    HTTPS link) into the Copilot chat instead of attaching the file. The link must
    be set to "anyone with the link can view" — auth-required URLs will fail.
    Downstream behavior matches /upload-file: same validation, same response shape.
    """
    url = _normalize_share_url(payload.url.strip())
    _validate_safe_url(url)

    try:
        async with httpx.AsyncClient(
            timeout=DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Download failed with HTTP {resp.status_code}",
                    )
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"File too large ({int(content_length) // (1024 * 1024)} MB); "
                            "limit is 25 MB"
                        ),
                    )

                buf = bytearray()
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    buf.extend(chunk)
                    if len(buf) > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail="Downloaded file exceeded 25 MB limit",
                        )
                derived_name = payload.filename or _filename_from_response(resp, url)
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {e}")

    filename = (derived_name or "leads.xlsx").strip()
    # Many direct-download URLs (Drive's `uc?export=download`) don't carry an extension
    # in the path; assume xlsx and let parse_excel validate the actual bytes.
    if not filename.lower().endswith((".xlsx", ".xls")):
        filename = f"{filename}.xlsx"

    return _stage_xlsx_bytes(bytes(buf), filename)