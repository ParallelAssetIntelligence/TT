import os
import re
import time
import logging
from serpapi import GoogleSearch
from app.models.lead import LeadRow, EnrichedData

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


def enrich_lead(lead: LeadRow) -> EnrichedData:
    """
    Query SerpAPI using ALL data from the row for maximum accuracy.
    e.g. if row has Company, Name, City, Industry — all get used in the search.
    """
    query = lead.search_text()
    logger.info(f"SerpAPI query: {query}")

    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set — returning empty enrichment")
        return EnrichedData()

    try:
        search = GoogleSearch({
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": 10,
        })
        results = search.get_dict()
        organic = results.get("organic_results", [])

        return _extract_smart_data(organic)

    except Exception as e:
        logger.error(f"SerpAPI error for '{query}': {e}")
        return EnrichedData()


def enrich_leads(leads: list[LeadRow]) -> list[EnrichedData]:
    """Enrich all leads. 1 second delay between API calls for rate limiting."""
    enriched = []
    for i, lead in enumerate(leads):
        enriched.append(enrich_lead(lead))
        if i < len(leads) - 1:
            time.sleep(1)
    logger.info(f"Enriched {len(enriched)} leads")
    return enriched


def _extract_smart_data(organic_results: list[dict]) -> EnrichedData:
    """
    Parse SerpAPI results to extract website, linkedin, title, description, location.
    Uses row_data to cross-reference and improve accuracy.
    """
    website = ""
    linkedin = ""
    title = ""
    description = ""
    location = ""

    for result in organic_results:
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        result_title = result.get("title", "")

        # Extract LinkedIn URL
        if not linkedin and "linkedin.com/in/" in link:
            linkedin = link
            if not title:
                title = _extract_title(result_title)

        # Extract company website
        if not website and _is_company_website(link):
            website = link
            if not description:
                description = _clean_snippet(snippet)

        # Extract location from snippets
        if not location:
            location = _extract_location(snippet)

    # Fallback description from first result
    if not description and organic_results:
        description = _clean_snippet(organic_results[0].get("snippet", ""))

    return EnrichedData(
        website=website,
        linkedin=linkedin,
        title=title,
        description=description,
        location=location,
    )


def _extract_title(result_title: str) -> str:
    """Extract job title from LinkedIn-style result title.
    e.g. 'John Smith - CEO at Acme Corp | LinkedIn' -> 'CEO'
    """
    match = re.search(r"-\s*(.+?)\s*(?:at|@)\s*", result_title)
    if match:
        return match.group(1).strip()
    # Try pattern: "Title - Company | LinkedIn"
    match = re.search(r"^(.+?)\s*-\s*(.+?)\s*\|", result_title)
    if match:
        return match.group(1).strip()
    return ""


def _is_company_website(url: str) -> bool:
    """Check if URL is likely a company website (not social media/aggregator)."""
    skip_domains = [
        "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
        "youtube.com", "wikipedia.org", "yelp.com", "bbb.org",
        "glassdoor.com", "crunchbase.com", "bloomberg.com", "zoominfo.com",
        "indeed.com", "google.com", "reddit.com", "github.com",
    ]
    return not any(domain in url for domain in skip_domains)


def _clean_snippet(snippet: str) -> str:
    """Clean a search snippet to a short description."""
    snippet = re.sub(r"\b\w{3}\s+\d{1,2},\s+\d{4}\b", "", snippet)
    snippet = snippet.replace("...", "").strip()
    sentences = snippet.split(". ")
    if sentences:
        return sentences[0].strip()[:150]
    return snippet[:150]


def _extract_location(snippet: str) -> str:
    """Extract city/state or city/country from snippet."""
    # "based in Austin, TX" or "located in Austin, Texas"
    match = re.search(
        r"(?:based in|located in|headquarters in|headquartered in|in)\s+"
        r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z]{2,})",
        snippet
    )
    if match:
        return match.group(1).strip()
    # Fallback: City, ST pattern anywhere
    match = re.search(r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z]{2})\b", snippet)
    if match:
        return match.group(1).strip()
    return ""
