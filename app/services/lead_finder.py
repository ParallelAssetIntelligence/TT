"""Find leads in the Excel file by name (fuzzy match).

Used by the Copilot bot endpoints when Matt asks about a lead by name —
the lead is stored in Tustin Group Lead Gen list.xlsx, not in a DB.
"""
import logging
from app.services.leads_reader import read_all_rows

logger = logging.getLogger(__name__)

DEFAULT_LEADS_FILE = "Tustin Group Lead Gen list.xlsx"

# Column name candidates — handles ZoomInfo exports with slight variations.
NAME_COLS = ["Name", "Full Name", "Contact Name"]
FIRST_NAME_COLS = ["First Name", "FirstName", "Given Name"]
LAST_NAME_COLS = ["Last Name", "LastName", "Surname", "Family Name"]


def _build_full_name(row_data: dict) -> str:
    """Construct the lead's full name from whatever name columns exist."""
    for col in NAME_COLS:
        if row_data.get(col):
            return row_data[col].strip()

    first = next((row_data[c] for c in FIRST_NAME_COLS if row_data.get(c)), "")
    last = next((row_data[c] for c in LAST_NAME_COLS if row_data.get(c)), "")
    return f"{first} {last}".strip()


def find_lead_by_name(name_query: str, file_path: str = DEFAULT_LEADS_FILE) -> dict | None:
    """Return the first lead whose full name contains the query (case-insensitive).

    Returns the matching row dict (row number + data) or None if no match.
    """
    if not name_query or not name_query.strip():
        return None

    query = name_query.lower().strip()
    all_rows = read_all_rows(file_path)

    # Exact full-name match first.
    for row in all_rows["rows"]:
        full_name = _build_full_name(row["data"]).lower()
        if full_name == query:
            return row

    # Fall back to substring match.
    for row in all_rows["rows"]:
        full_name = _build_full_name(row["data"]).lower()
        if query in full_name or all(part in full_name for part in query.split()):
            return row

    return None


def row_to_lead_record(row: dict) -> dict:
    """Normalize an Excel row into the LeadRecord schema the Copilot API returns."""
    data = row["data"]
    return {
        "row": row["row"],
        "name": _build_full_name(data),
        "company": data.get("Company", ""),
        "title": data.get("Title", ""),
        "phone": data.get("Phone", ""),
        "email": data.get("Email", ""),
        "city": data.get("City", ""),
        "state": data.get("State", ""),
        "linkedin_url": data.get("Enriched_LinkedIn", ""),
        "linkedin_headline": data.get("Enriched_LinkedIn_Headline", ""),
        "linkedin_summary": data.get("Enriched_LinkedIn_Summary", ""),
        "tenure_months": _as_int_or_none(data.get("Enriched_Tenure_Months")),
        "tenure_label": data.get("Enriched_Tenure_Label", ""),
        "prior_company_1": data.get("Enriched_Prior_Company_1", ""),
        "prior_company_2": data.get("Enriched_Prior_Company_2", ""),
        "title_qualifier": data.get("Enriched_Title_Qualifier", ""),
        "signal_tag": data.get("Enriched_Signal_Tag", ""),
        "script_used": data.get("Enriched_Script_Used", ""),
        "personalized_opener": data.get("Enriched_Personalized_Opener", ""),
    }


def _as_int_or_none(v) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
