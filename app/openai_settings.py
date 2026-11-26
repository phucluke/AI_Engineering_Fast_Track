"""Shared OpenAI-compatible client settings. Works with OpenAI or OpenRouter."""
import os

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"

def resolve_openai(env: dict | None = None) -> dict:
    """Read OPENAI_API_KEY, OPENAI_MODEL, OPENAI_BASE_URL (and optional headers/timeout).

    OpenRouter: set OPENAI_BASE_URL=https://openrouter.ai/api/v1 and use an OpenRouter key/model.
    Direct OpenAI: leave BASE_URL unset (defaults to api.openai.com) and use an OpenAI key/model.
    """
    env = os.environ if env is None else env
    key = str(env.get("OPENAI_API_KEY", "")).strip()
    model = str(env.get("OPENAI_MODEL", "")).strip()
    base = str(env.get("OPENAI_BASE_URL", "")).strip() or DEFAULT_OPENAI_BASE_URL
    if not key or key.startswith("replace"):
        raise RuntimeError("Set OPENAI_API_KEY in .env. Do not commit .env.")
    if not model or model.startswith("choose_"):
        raise RuntimeError("Set OPENAI_MODEL in .env, for example gpt-4o-mini or openai/gpt-4o-mini.")
    headers = {}
    referer = str(env.get("OPENAI_HTTP_REFERER", "")).strip()
    title = str(env.get("OPENAI_APP_TITLE", "")).strip()
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title
    timeout = float(str(env.get("OPENAI_TIMEOUT_SEC", "")).strip() or "30")
    max_retries = int(str(env.get("OPENAI_MAX_RETRIES", "")).strip() or "3")
    return {
        "api_key": key,
        "base_url": base,
        "model": model,
        "default_headers": headers,
        "timeout": timeout,
        "max_retries": max_retries,
    }
