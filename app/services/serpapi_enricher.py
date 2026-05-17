import os
import re
import time
import logging
from serpapi import GoogleSearch
from app.models.lead import LeadRow, EnrichedData
from app.services.intelligence import analyze_and_write_opener

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")


def enrich_lead(lead: LeadRow, run_intelligence: bool = True) -> EnrichedData:
    """
    Query SerpAPI using ALL data from the row for maximum accuracy.
    e.g. if row has Company, Name, City, Industry — all get used in the search.

    When `run_intelligence` is True (default), also runs the LLM intelligence
    layer to fill tenure / prior companies / title qualifier / signal tag
    and write a personalized opener using Tustin's 6 scripts.
    """
    query = lead.search_text()
    logger.info(f"SerpAPI query: {query}")

    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set — returning empty enrichment")
        enriched = EnrichedData()
    else:
        try:
            search = GoogleSearch({
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 10,
            })
            results = search.get_dict()
            organic = results.get("organic_results", [])
            enriched = _extract_smart_data(organic)
        except Exception as e:
            logger.error(f"SerpAPI error for '{query}': {e}")
            enriched = EnrichedData()

    if run_intelligence:
        intel = analyze_and_write_opener(lead, enriched)
        enriched.tenure_months = intel["tenure_months"]
        enriched.tenure_label = intel["tenure_label"]
        enriched.prior_company_1 = intel["prior_company_1"]
        enriched.prior_company_2 = intel["prior_company_2"]
        enriched.title_qualifier = intel["title_qualifier"]
        enriched.signal_tag = intel["signal_tag"]
        enriched.script_used = intel["script_used"]
        enriched.personalized_opener = intel["personalized_opener"]

    return enriched


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
    Parse SerpAPI results to extract:
      - website, linkedin (personal), title, description, location
      - linkedin_headline, linkedin_summary (from linkedin.com/in/ result)
      - linkedin_company_description (from linkedin.com/company/ result)
    """
    website = ""
    linkedin = ""
    linkedin_headline = ""
    linkedin_summary = ""
    linkedin_company_description = ""
    title = ""
    description = ""
    location = ""

    for result in organic_results:
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        result_title = result.get("title", "")

        # LinkedIn personal profile → URL, headline, summary
        if not linkedin and "linkedin.com/in/" in link:
            linkedin = link
            linkedin_headline = _extract_linkedin_headline(result_title)
            linkedin_summary = _clean_long_text(snippet, max_len=400)
            if not title:
                title = _extract_title(result_title)

        # LinkedIn company page → company description
        elif not linkedin_company_description and "linkedin.com/company/" in link:
            linkedin_company_description = _clean_long_text(snippet, max_len=400)

        # Company website
        if not website and _is_company_website(link):
            website = link
            if not description:
                description = _clean_snippet(snippet)

        # Location
        if not location:
            location = _extract_location(snippet)

    # Fallback description from first result
    if not description and organic_results:
        description = _clean_snippet(organic_results[0].get("snippet", ""))

    return EnrichedData(
        website=website,
        linkedin=linkedin,
        linkedin_headline=linkedin_headline,
        linkedin_summary=linkedin_summary,
        linkedin_company_description=linkedin_company_description,
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


def _extract_linkedin_headline(result_title: str) -> str:
    """Extract the headline portion from a LinkedIn result title.
    e.g. 'John Smith - CEO at Acme Corp | LinkedIn' -> 'CEO at Acme Corp'
    """
    s = re.sub(r"\s*[\|\-]?\s*LinkedIn\s*$", "", result_title, flags=re.IGNORECASE).strip()
    parts = s.split(" - ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return s.strip()


def _clean_long_text(snippet: str, max_len: int = 400) -> str:
    """Clean a snippet but keep multiple sentences, truncated to max_len."""
    snippet = re.sub(r"\b\w{3}\s+\d{1,2},\s+\d{4}\b", "", snippet)
    snippet = snippet.replace("...", "").strip()
    return snippet[:max_len].strip()


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
