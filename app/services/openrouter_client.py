"""Thin wrapper around the OpenRouter chat completions API.

OpenRouter exposes an OpenAI-compatible REST endpoint so we just use httpx.
"""
import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
DEFAULT_TIMEOUT = 45.0


class OpenRouterError(RuntimeError):
    pass


def chat_json(system: str, user: str, model: str | None = None, temperature: float = 0.3) -> dict:
    """Send a chat request and parse the assistant's reply as JSON.

    The model is instructed to return strict JSON. We strip code fences and
    parse. Raises OpenRouterError on transport, status, or JSON failures.
    """
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise OpenRouterError("OPENROUTER_API_KEY is not set")

    payload = {
        "model": model or DEFAULT_MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://tustin.local",
        "X-Title": "Tustin Sales Co-Pilot",
    }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            r = client.post(OPENROUTER_URL, headers=headers, json=payload)
    except httpx.HTTPError as e:
        raise OpenRouterError(f"transport error: {e}") from e

    if r.status_code >= 400:
        raise OpenRouterError(f"HTTP {r.status_code}: {r.text[:400]}")

    body = r.json()
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise OpenRouterError(f"unexpected response shape: {body}") from e

    text = content.strip()
    # Strip Markdown code fences if the model wrapped JSON in ```json ... ```
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise OpenRouterError(f"non-JSON content: {text[:300]}") from e
