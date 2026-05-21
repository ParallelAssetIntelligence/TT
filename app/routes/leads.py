import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import Response
from app.services.excel_parser import parse_excel, write_enriched_excel
from app.services.serpapi_enricher import enrich_leads
from app.services.row_enricher import enrich_row_range, parse_row_range
from app.services.leads_reader import read_row, read_all_rows
from app.services.leads_exporter import fetch_leads, leads_to_xlsx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["Leads"])

DEFAULT_LEADS_FILE = "Tustin Group Lead Gen list.xlsx"


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
async def enrich_row(
    rows: str = Query(
        ...,
        description="Excel row(s) to enrich. Single row: '2'. Range: '2-10'. Row 1 is the header.",
        examples=["2", "2-10"],
    ),
):
    """
    Enrich one row or a range of rows in Tustin Group Lead Gen list.xlsx
    and save back to the same file.

    Adds Enriched_* columns (Website, LinkedIn, Title, Description, Location)
    only for the requested rows, leaving original columns untouched.
    """
    try:
        start, end = parse_row_range(rows)
        result = enrich_row_range(DEFAULT_LEADS_FILE, start, end)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(
            status_code=409,
            detail=(
                f"'{DEFAULT_LEADS_FILE}' is open in another program (likely Excel). "
                "Close the file and try again."
            ),
        )
    except Exception as e:
        logger.exception("Row enrichment failed")
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {e}")

    return {"file": DEFAULT_LEADS_FILE, "rows": rows, **result}


@router.get("/rows")
async def get_all_rows(
    limit: int | None = Query(
        None,
        ge=1,
        description="Max number of rows to return. Omit to return everything.",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of data rows to skip from the start (0-indexed).",
    ),
):
    """Return all leads from Tustin Group Lead Gen list.xlsx as JSON."""
    try:
        return {"file": DEFAULT_LEADS_FILE, **read_all_rows(DEFAULT_LEADS_FILE, limit, offset)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/rows/{row}")
async def get_row(row: int):
    """Return a single lead by Excel row number (row 1 = header, row 2 = first lead)."""
    try:
        return {"file": DEFAULT_LEADS_FILE, **read_row(DEFAULT_LEADS_FILE, row)}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/download")
async def download_enriched_leads(
    source_file: str | None = Query(
        None,
        description=(
            "Filter to leads originating from this uploaded file (e.g. "
            "'20260521_220636_test_leads.xlsx'). Omit to download every lead."
        ),
    ),
    limit: int = Query(5000, ge=1, le=20000),
):
    """Download enriched leads from the Supabase `leads` table as an xlsx.

    Linked from the Teams notification card so Matt can grab a per-upload
    spreadsheet with all enrichment columns filled in (LinkedIn, tenure,
    opener, etc.) without re-uploading the original file.
    """
    try:
        rows = fetch_leads(source_file=source_file, limit=limit)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No leads found for source_file={source_file!r}"
                if source_file
                else "No leads in the leads table"
            ),
        )

    xlsx_bytes = leads_to_xlsx(rows)

    # Friendly attachment name — derived from the source file if provided.
    if source_file:
        stem = source_file.rsplit(".", 1)[0]
        out_name = f"{stem}_enriched.xlsx"
    else:
        out_name = f"leads_enriched_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
