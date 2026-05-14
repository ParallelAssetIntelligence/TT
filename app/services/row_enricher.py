import logging
from pathlib import Path
from openpyxl import load_workbook
from app.models.lead import LeadRow, EnrichedData
from app.services.serpapi_enricher import enrich_lead

logger = logging.getLogger(__name__)

ENRICHED_COLUMNS = [
    "Enriched_Website",
    "Enriched_LinkedIn",
    "Enriched_Title",
    "Enriched_Description",
    "Enriched_Location",
]


def enrich_specific_row(file_path: str, row_number: int) -> dict:
    """
    Enrich a specific Excel row and write the result back to the same file.

    row_number is the actual Excel row (row 1 = header, row 2 = first data row).
    Appends Enriched_* columns if missing, then fills them on the target row only.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    wb = load_workbook(filename=str(path))
    ws = wb.active

    if row_number < 2 or row_number > ws.max_row:
        raise ValueError(
            f"row must be between 2 and {ws.max_row} (row 1 is the header)"
        )

    headers = [
        str(c.value).strip() if c.value is not None else f"Column_{i}"
        for i, c in enumerate(ws[1])
    ]

    # Append any missing Enriched_* columns at the end of the header row
    for col_name in ENRICHED_COLUMNS:
        if col_name not in headers:
            new_idx = len(headers) + 1
            ws.cell(row=1, column=new_idx, value=col_name)
            headers.append(col_name)

    # Read the target row's data, skipping the Enriched_* columns for the search query
    original_count = len(headers) - len(ENRICHED_COLUMNS)
    row_cells = ws[row_number]
    row_data: dict[str, str] = {}
    for i, header in enumerate(headers[:original_count]):
        cell_val = row_cells[i].value if i < len(row_cells) else None
        row_data[header] = str(cell_val).strip() if cell_val is not None else ""

    if not any(row_data.values()):
        raise ValueError(f"Row {row_number} is empty")

    lead = LeadRow(headers=headers[:original_count], data=row_data)
    enriched: EnrichedData = enrich_lead(lead)

    values = {
        "Enriched_Website": enriched.website,
        "Enriched_LinkedIn": enriched.linkedin,
        "Enriched_Title": enriched.title,
        "Enriched_Description": enriched.description,
        "Enriched_Location": enriched.location,
    }
    for col_name, val in values.items():
        col_idx = headers.index(col_name) + 1
        ws.cell(row=row_number, column=col_idx, value=val or "")

    wb.save(str(path))
    logger.info(f"Row {row_number} enriched and saved to {path.name}")

    return {
        "row": row_number,
        "search_query": lead.search_text(),
        "original": row_data,
        "enriched": values,
    }
