from pydantic import BaseModel
from typing import Optional


class LeadRow(BaseModel):
    """A single row from the client's Excel — any columns, stored as a dict."""
    headers: list[str]          # original column names
    data: dict[str, str]        # column_name -> value (all strings)

    def search_text(self) -> str:
        """Combine all non-empty values into a single search string.

        Skips Enriched_* columns so previously-saved enrichment data is not
        fed back into a new query (would happen on /upload of a file that
        was already enriched).
        """
        parts = [
            v for k, v in self.data.items()
            if v and v.strip() and not k.startswith("Enriched_")
        ]
        return " ".join(parts)


class EnrichedData(BaseModel):
    """Smart data extracted from SerpAPI + LLM intelligence layer."""
    # SerpAPI-extracted
    website: Optional[str] = ""
    linkedin: Optional[str] = ""
    linkedin_headline: Optional[str] = ""
    linkedin_summary: Optional[str] = ""
    linkedin_company_description: Optional[str] = ""
    title: Optional[str] = ""
    description: Optional[str] = ""
    location: Optional[str] = ""

    # LLM-derived signals (Step 2 intelligence)
    tenure_months: Optional[int] = None
    tenure_label: Optional[str] = ""          # NEW_HIRE | LONG_TENURED | MID_TENURE | UNKNOWN
    prior_company_1: Optional[str] = ""
    prior_company_2: Optional[str] = ""
    title_qualifier: Optional[str] = ""       # DECISION_MAKER | INFLUENCER | IN_HOUSE | UNKNOWN
    signal_tag: Optional[str] = ""            # OLDER_BUILDING | NEW_OCCUPANT | OWNERSHIP_CHANGE | PERMIT | ENERGY | REACTIVE | NEW_HIRE | LONG_TENURED | CAREER_MOVER

    # Step 3 — Personalized opener
    script_used: Optional[str] = ""           # e.g. "Script 1: Older Building"
    personalized_opener: Optional[str] = ""
