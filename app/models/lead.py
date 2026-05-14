from pydantic import BaseModel
from typing import Optional


class LeadRow(BaseModel):
    """A single row from the client's Excel — any columns, stored as a dict."""
    headers: list[str]          # original column names
    data: dict[str, str]        # column_name -> value (all strings)

    def search_text(self) -> str:
        """Combine all non-empty values into a single search string."""
        parts = [v for v in self.data.values() if v and v.strip()]
        return " ".join(parts)


class EnrichedData(BaseModel):
    """Smart data extracted from SerpAPI."""
    website: Optional[str] = ""
    linkedin: Optional[str] = ""
    title: Optional[str] = ""
    description: Optional[str] = ""
    location: Optional[str] = ""
