"""Step 2 (signal analysis) + Step 3 (script + opener) in a single LLM call.

Given the raw lead row + SerpAPI-extracted LinkedIn/web data, the model:
  1. Infers tenure (months), tenure label, prior companies, title qualifier.
  2. Picks the best-fit Tustin cold-call script from the 6 in context/script.md.
  3. Writes a 2–3 sentence personalized opener that adapts that script
     to this specific contact.

All 6 scripts are embedded in the system prompt so the model can pick the
right one and follow Matt's tone exactly.
"""
import logging
from app.models.lead import LeadRow, EnrichedData
from app.services.openrouter_client import chat_json, OpenRouterError

logger = logging.getLogger(__name__)

# All 6 Tustin scripts + objection handlers, copy-pasted from context/script.md.
SCRIPTS_REFERENCE = """\
TUSTIN GROUP — COLD CALL SCRIPTS (pick the best fit for this lead):

SCRIPT 1 — Older / Historic Building
Trigger: building 30+ years old, especially pre-1990s.
"Hi, this is Matt calling from The Tustin Group — we're a commercial building services company out of the [Location] area. Quick question — I noticed your building was constructed back in [year/era], and older buildings like yours often have HVAC systems either well past their service life or running on a patchwork of different vendors. We specialize in commercial buildings in the greater [Location] area — 10,000 square feet and up — and we've been keeping those kinds of systems running reliably since 1992. Are you currently locked into a service agreement, or is that something you're managing on a reactive basis right now?"

SCRIPT 2 — New Building Occupant / Tenant Move-In
Trigger: business recently moved into new space, new lease signed.
"Hi, this is Matt from The Tustin Group. Congratulations on the new space — I saw that [Company] recently moved into [address/building]. One of the first things that falls through the cracks in a new occupancy is locking in a reliable HVAC and building systems partner — most tenants inherit whatever the previous occupant had, and that's usually a mess. We work with commercial buildings throughout [Location] and we offer a free building assessment so you know exactly what you're working with before something breaks. Would that be worth 20 minutes of your time?"

SCRIPT 3 — Building Ownership / Management Change
Trigger: property sold, new property management, operator transition.
"Hi, this is Matt calling from The Tustin Group. I saw that [building/property] recently changed hands — congratulations. New ownership transitions are actually one of the most common times we get called in, because the incoming team usually doesn't know the service history on the mechanical systems and wants a fresh set of eyes. We're an integrated building services company — HVAC, water treatment, fire safety, plumbing — so we can give you a comprehensive picture of where the building stands. Would it make sense to schedule a walkthrough while you're still in the onboarding phase?"

SCRIPT 4 — Building Permit / Recent Renovation
Trigger: recent permit pulled for renovation, buildout, or addition.
"Hi, this is Matt from The Tustin Group. I noticed a permit was recently filed for work at [address] — renovations and buildouts almost always create HVAC needs that either weren't planned for or get bolted on last minute. That's where systems start to underperform and energy costs creep up. We've handled retrofits and new installations for commercial buildings across [Location] for over 30 years. Are you already working with a mechanical contractor on this project, or is that still open?"

SCRIPT 5 — Energy / Utility Efficiency
Trigger: high-energy building types — office parks, medical, industrial, manufacturing.
"Hi, this is Matt from The Tustin Group. We work with commercial building operators in [Location] and one of the most common conversations we're having right now is around energy costs — specifically, buildings where the HVAC is running but nobody's really optimized it in years. We have an energy solutions team that does web-based monitoring and predictive maintenance — it's not just service calls when something breaks, it's getting ahead of it and cutting your operating costs in the process. Do you have a sense of what your current HVAC spend looks like annually?"

SCRIPT 6 — No Service Agreement / Reactive-Only
Trigger: prospect calls vendors ad hoc, no contract in place.
"Hi, this is Matt from The Tustin Group. I'm reaching out because we work with a number of commercial building operators in the area who don't currently have a service agreement in place — they're just calling someone when something goes down. I totally get it, but the math usually flips once you factor in emergency rates and equipment replacement costs. We offer structured service agreements for buildings 10,000 square feet and up, and they're designed to reduce your total cost of ownership, not just keep the lights on. Would it be worth a 15-minute conversation to see if it pencils out for your building?"

UNIVERSAL OBJECTION HANDLERS (do not put in opener, just be aware):
- "We already have a vendor." → "Great — when's your agreement up? We're not looking to disrupt anything, just want to be on your radar when it's time to benchmark."
- "We handle it in-house." → "Understood — do you have in-house coverage for water treatment and fire systems too, or just mechanical? A lot of our clients use us to fill the gaps."
- "Send me something by email." → "Happy to — what's most relevant for you right now, the maintenance side or energy efficiency?"
- "Not the right person." → "No problem — who manages the building systems decisions? Is that facilities, property management, or ownership?"
"""

SYSTEM_PROMPT = f"""You are a sales intelligence agent for The Tustin Group, a commercial building services company (HVAC, water treatment, fire safety, plumbing). Their target customers are commercial buildings 10,000 sq ft and up.

Your job: given a raw lead row + LinkedIn/web data we already scraped, extract structured signals AND write a personalized cold-call opener for Matt (the sales rep).

{SCRIPTS_REFERENCE}

RULES FOR YOUR OUTPUT:
1. Output ONLY valid JSON — no prose, no markdown fences.
2. Pick the SINGLE best-fit script (1-6). If none fit cleanly, pick the closest one and adapt it.
3. The opener must be 2–3 sentences, conversational, in Matt's voice (warm, direct, never pushy).
4. Replace [Location], [Company], [year/era], [address] with real values from the lead data. If a value is unknown, omit that placeholder gracefully — don't leave brackets in the final text.
5. If the contact is a "Maintenance Manager" / "Maintenance Tech" / janitor-level title → title_qualifier = "IN_HOUSE" (Matt should NOT pitch them — they don't make vendor decisions).
6. "Director", "VP", "Chief", "Owner", "President", "Principal", "Manager of Operations/Facilities" → "DECISION_MAKER".
7. "Facilities Coordinator", "Operations Coordinator", "Assistant" → "INFLUENCER".
8. tenure_months: integer — months at current company based on LinkedIn data. null if unknown.
9. tenure_label: "NEW_HIRE" (<12 mo), "MID_TENURE" (12–59 mo), "LONG_TENURED" (60+ mo), or "UNKNOWN".
10. signal_tag: one of OLDER_BUILDING, NEW_OCCUPANT, OWNERSHIP_CHANGE, PERMIT, ENERGY, REACTIVE, NEW_HIRE, LONG_TENURED, CAREER_MOVER, UNKNOWN.

EXACT JSON SCHEMA:
{{
  "tenure_months": <int or null>,
  "tenure_label": "NEW_HIRE" | "MID_TENURE" | "LONG_TENURED" | "UNKNOWN",
  "prior_company_1": "<company name or empty string>",
  "prior_company_2": "<company name or empty string>",
  "title_qualifier": "DECISION_MAKER" | "INFLUENCER" | "IN_HOUSE" | "UNKNOWN",
  "signal_tag": "<one of the tags above>",
  "script_used": "Script 1: Older Building" | "Script 2: New Occupant" | "Script 3: Ownership Change" | "Script 4: Permit/Renovation" | "Script 5: Energy" | "Script 6: Reactive",
  "personalized_opener": "<2-3 sentence opener in Matt's voice>"
}}
"""


def _build_user_prompt(lead: LeadRow, enriched: EnrichedData) -> str:
    """Render the lead + scraped data into a compact prompt block."""
    raw_row = "\n".join(f"  - {k}: {v}" for k, v in lead.data.items() if v)
    return (
        "LEAD ROW (from ZoomInfo export):\n"
        f"{raw_row}\n\n"
        "SCRAPED FROM LINKEDIN / WEB SEARCH:\n"
        f"  - linkedin_url: {enriched.linkedin}\n"
        f"  - linkedin_headline: {enriched.linkedin_headline}\n"
        f"  - linkedin_summary: {enriched.linkedin_summary}\n"
        f"  - company_description: {enriched.linkedin_company_description}\n"
        f"  - inferred_title: {enriched.title}\n"
        f"  - website_description: {enriched.description}\n"
        f"  - location: {enriched.location}\n\n"
        "Return the JSON now."
    )


def analyze_and_write_opener(lead: LeadRow, enriched: EnrichedData) -> dict:
    """Run the single LLM call and return a dict of intelligence fields.

    On any failure, return safe empty defaults so the pipeline keeps going.
    """
    try:
        result = chat_json(
            system=SYSTEM_PROMPT,
            user=_build_user_prompt(lead, enriched),
            temperature=0.4,
        )
    except OpenRouterError as e:
        logger.warning(f"OpenRouter intelligence call failed: {e}")
        return _empty_result()

    return {
        "tenure_months": _as_int(result.get("tenure_months")),
        "tenure_label": _as_str(result.get("tenure_label"), "UNKNOWN"),
        "prior_company_1": _as_str(result.get("prior_company_1")),
        "prior_company_2": _as_str(result.get("prior_company_2")),
        "title_qualifier": _as_str(result.get("title_qualifier"), "UNKNOWN"),
        "signal_tag": _as_str(result.get("signal_tag"), "UNKNOWN"),
        "script_used": _as_str(result.get("script_used")),
        "personalized_opener": _as_str(result.get("personalized_opener")),
    }


def _empty_result() -> dict:
    return {
        "tenure_months": None,
        "tenure_label": "UNKNOWN",
        "prior_company_1": "",
        "prior_company_2": "",
        "title_qualifier": "UNKNOWN",
        "signal_tag": "UNKNOWN",
        "script_used": "",
        "personalized_opener": "",
    }


def _as_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_str(v, default: str = "") -> str:
    if v is None:
        return default
    return str(v).strip() or default
