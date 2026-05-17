"""Pre-call brief + live-call suggestion generators for the Tustin Teams bot.

Both endpoints lean on the OpenRouter LLM client and the same 6-script
playbook used during enrichment (intelligence.py). The brief expands the
existing enrichment into a full call-prep document; the live suggestion
turns whatever the prospect just said into Matt's next sentence.
"""
import logging
from app.services.openrouter_client import chat_json, OpenRouterError
from app.services.intelligence import SCRIPTS_REFERENCE

logger = logging.getLogger(__name__)


BRIEF_SYSTEM_PROMPT = f"""You are a sales-prep assistant for Matt, a rep at The Tustin Group (commercial building services — HVAC, water treatment, fire safety, plumbing; target buildings 10,000+ sq ft).

Your job: take an enriched lead record and produce a structured PRE-CALL BRIEF Matt can read in 10 seconds before dialing.

{SCRIPTS_REFERENCE}

RULES:
1. Output ONLY valid JSON — no prose, no markdown fences.
2. The recommended_opener must reuse / lightly polish the enriched opener already on the lead. Don't write a brand new one unless the existing one is missing.
3. likely_objections: exactly 2 objections the prospect is most likely to raise given their title/tenure/signal, with Matt's response for each.
4. follow_up_questions: 2 discovery questions Matt can use to advance the conversation.
5. recommendation: one short sentence — the *strategic* note (e.g. "Don't pitch directly, ask for the decision-maker" if title_qualifier is IN_HOUSE).
6. If a field is unknown on the lead, write "unknown" — do not invent.

EXACT JSON SCHEMA:
{{
  "name": "<full name>",
  "company": "<company>",
  "title": "<title>",
  "title_qualifier": "DECISION_MAKER|INFLUENCER|IN_HOUSE|UNKNOWN",
  "signal_tag": "<one of the signal tags>",
  "tenure_months": <int or null>,
  "prior_companies": ["<name>", "<name>"],
  "recommendation": "<one-sentence strategy note>",
  "recommended_opener": "<2-3 sentence opener in Matt's voice>",
  "script_used": "<e.g. 'Script 6: Reactive'>",
  "likely_objections": [
    {{"says": "<what they might say>", "respond": "<Matt's response>"}},
    {{"says": "<what they might say>", "respond": "<Matt's response>"}}
  ],
  "follow_up_questions": ["<question>", "<question>"]
}}
"""


RESPOND_SYSTEM_PROMPT = f"""You are Matt's real-time call assistant for The Tustin Group. Matt is ON A LIVE PHONE CALL right now and just typed what the prospect said. You must respond with the next sentence Matt should say.

{SCRIPTS_REFERENCE}

RULES:
1. Output ONLY valid JSON — no prose, no markdown fences.
2. suggestion: max 2 sentences, max 30 words total. Matt has to say this aloud immediately.
3. Match Matt's voice: warm, direct, confident, never pushy. Sound like a human, not a script.
4. If the prospect raised an objection, use the universal objection handlers as a base — adapt to the specific wording.
5. intent_detected: classify what the prospect said as one of:
   - VENDOR_LOCKED (already has a vendor)
   - NOT_INTERESTED (cold refusal)
   - PRICE_QUESTION (asking about cost)
   - GATEKEEPER (wrong person / blocking)
   - INTERESTED (positive signal)
   - OTHER

EXACT JSON SCHEMA:
{{
  "suggestion": "<1-2 sentence response, max 30 words>",
  "intent_detected": "VENDOR_LOCKED|NOT_INTERESTED|PRICE_QUESTION|GATEKEEPER|INTERESTED|OTHER"
}}
"""


def generate_brief(lead: dict) -> dict:
    """Generate a pre-call brief for the given enriched lead record."""
    user_prompt = (
        "ENRICHED LEAD RECORD:\n"
        f"  name: {lead.get('name')}\n"
        f"  company: {lead.get('company')}\n"
        f"  title: {lead.get('title')}\n"
        f"  title_qualifier: {lead.get('title_qualifier')}\n"
        f"  signal_tag: {lead.get('signal_tag')}\n"
        f"  tenure_months: {lead.get('tenure_months')}\n"
        f"  tenure_label: {lead.get('tenure_label')}\n"
        f"  prior_company_1: {lead.get('prior_company_1')}\n"
        f"  prior_company_2: {lead.get('prior_company_2')}\n"
        f"  city: {lead.get('city')}\n"
        f"  state: {lead.get('state')}\n"
        f"  linkedin_headline: {lead.get('linkedin_headline')}\n"
        f"  linkedin_summary: {lead.get('linkedin_summary')}\n"
        f"  existing_opener: {lead.get('personalized_opener')}\n"
        f"  existing_script_used: {lead.get('script_used')}\n\n"
        "Return the JSON brief now."
    )

    try:
        result = chat_json(
            system=BRIEF_SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.4,
        )
    except OpenRouterError as e:
        logger.warning(f"Brief generation failed: {e}")
        return _fallback_brief(lead)

    # Make sure required fields are present.
    result.setdefault("name", lead.get("name", ""))
    result.setdefault("company", lead.get("company", ""))
    result.setdefault("recommended_opener", lead.get("personalized_opener", ""))
    result.setdefault("script_used", lead.get("script_used", ""))
    return result


def generate_live_suggestion(prospect_said: str, lead: dict | None = None) -> dict:
    """Generate Matt's next-sentence response during a live call."""
    lead_context = ""
    if lead:
        lead_context = (
            "CURRENT CALL CONTEXT:\n"
            f"  Talking to: {lead.get('name')} ({lead.get('title')} at {lead.get('company')})\n"
            f"  Signal: {lead.get('signal_tag')} / {lead.get('title_qualifier')}\n"
            f"  Tenure: {lead.get('tenure_months')} months\n\n"
        )

    user_prompt = (
        f"{lead_context}"
        f"PROSPECT JUST SAID: \"{prospect_said}\"\n\n"
        "Return the JSON with Matt's next sentence now."
    )

    try:
        result = chat_json(
            system=RESPOND_SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.5,
        )
    except OpenRouterError as e:
        logger.warning(f"Live suggestion failed: {e}")
        return {
            "suggestion": "Got it — totally understand. Mind if I send you a quick one-pager so you have it when timing's better?",
            "intent_detected": "OTHER",
        }

    return {
        "suggestion": str(result.get("suggestion", "")).strip(),
        "intent_detected": str(result.get("intent_detected", "OTHER")).strip().upper(),
    }


def _fallback_brief(lead: dict) -> dict:
    """Used if the LLM call fails — return whatever we already have on file."""
    return {
        "name": lead.get("name", ""),
        "company": lead.get("company", ""),
        "title": lead.get("title", ""),
        "title_qualifier": lead.get("title_qualifier", "UNKNOWN"),
        "signal_tag": lead.get("signal_tag", "UNKNOWN"),
        "tenure_months": lead.get("tenure_months"),
        "prior_companies": [
            c for c in [lead.get("prior_company_1"), lead.get("prior_company_2")] if c
        ],
        "recommendation": "Brief generation temporarily unavailable — using cached enrichment only.",
        "recommended_opener": lead.get("personalized_opener", ""),
        "script_used": lead.get("script_used", ""),
        "likely_objections": [],
        "follow_up_questions": [],
    }
