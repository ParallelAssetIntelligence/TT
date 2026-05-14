import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.services.excel_parser import parse_excel, write_enriched_excel
from app.services.serpapi_enricher import enrich_leads
from app.services.row_enricher import enrich_specific_row

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["Leads"])

DEFAULT_LEADS_FILE = "Tustin Group Lead Gen list.xlsx"


class EnrichRowRequest(BaseModel):
    row: int
    file: str | None = None


@router.post("/upload")
async def upload_leads(file: UploadFile = File(...)):
    """
    Upload any Excel file → enrich with SerpAPI → return enriched Excel.

    Accepts any columns. Uses all row data to build accurate search queries.
    Appends 5 smart columns: Website, LinkedIn, Title, Description, Location.
    """
    # Step 1: Validate file type
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx or .xls files are accepted")

    # Step 2: Parse Excel (any columns)
    try:
        file_bytes = await file.read()
        leads = parse_excel(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Excel parse error: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse Excel file")

    if not leads:
        raise HTTPException(status_code=400, detail="No leads found in the Excel file")

    logger.info(f"Parsed {len(leads)} leads with columns: {leads[0].headers}")

    # Step 3: Enrich with SerpAPI (uses ALL row data for search)
    enrichments = enrich_leads(leads)

    # Step 4: Write enriched Excel (original columns + smart columns)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"leads_enriched_{timestamp}.xlsx"
    output_bytes = write_enriched_excel(leads, enrichments)

    # Step 5: Return as downloadable file
    return Response(
        content=output_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={output_filename}"},
    )


@router.post("/enrich-row")
async def enrich_row(payload: EnrichRowRequest):
    """
    Enrich a single row in the on-disk leads Excel and save it back in place.

    `row` is the Excel row number (row 1 is the header, row 2 is the first lead).
    `file` is optional; defaults to "Tustin Group Lead Gen list.xlsx".
    Adds Enriched_* columns (Website, LinkedIn, Title, Description, Location)
    only for the requested row, leaving original columns untouched.
    """
    file_path = payload.file or DEFAULT_LEADS_FILE
    try:
        result = enrich_specific_row(file_path, payload.row)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Row enrichment failed")
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {e}")

    return {"file": file_path, **result}
