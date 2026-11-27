"""Meeting-notes extraction via OpenAI-compatible API (OpenAI or OpenRouter)."""
from pathlib import Path
import logging, time
from openai import (
    APIStatusError, APITimeoutError, InternalServerError, OpenAI, RateLimitError,
)
from pydantic import ValidationError
from app.openai_settings import resolve_openai
from app.schemas import AnalyzeMeetingResponse

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "evidence" / "W02" / "system_prompt.md"

class UpstreamTimeoutError(Exception):
    """Upstream LLM timed out after retries."""

class UpstreamRateLimitError(Exception):
    """Upstream LLM returned 429 after retries."""

class UpstreamServerError(Exception):
    """Upstream LLM returned HTTP 500 (or other 5xx except 503) after retries."""

class UpstreamUnavailableError(Exception):
    """Upstream LLM returned HTTP 503 (model overloaded) after retries."""

class InvalidModelOutputError(Exception):
    """Model reply could not be validated against the response schema."""

def load_system_prompt(path: Path = PROMPT_PATH, version: str = "v1") -> str:
    version = version.lower()
    text = path.read_text(encoding="utf-8")
    start = f"<!-- SYSTEM {version.upper()} -->"
    end = f"<!-- /SYSTEM {version.upper()} -->"
    try:
        body = text.split(start, 1)[1].split(end, 1)[0]
    except IndexError as exc:
        raise ValueError(f"missing {start} block in {path}") from exc
    body = body.strip()
    if not body:
        raise ValueError(f"empty prompt {version}")
    return body

def _retry_after_seconds(exc: APIStatusError, attempt: int) -> float:
    headers = getattr(exc, "response", None)
    headers = getattr(headers, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is not None:
        try:
            return max(float(raw), 0.1)
        except (TypeError, ValueError):
            pass
    return min(2 ** attempt, 8)

class LLMService:
    def __init__(self, client: OpenAI | None = None, model: str | None = None,
                 max_retries: int | None = None, system_prompt: str | None = None):
        if client is None:
            settings = resolve_openai()
            self.client = OpenAI(
                api_key=settings["api_key"],
                base_url=settings["base_url"],
                default_headers=settings["default_headers"] or None,
                timeout=settings["timeout"],
            )
            self.model = model or settings["model"]
            self.max_retries = max_retries if max_retries is not None else settings["max_retries"]
        else:
            self.client = client
            if not model:
                raise ValueError("model is required when client is injected")
            self.model = model
            self.max_retries = max_retries if max_retries is not None else 3
        self.system_prompt = system_prompt if system_prompt is not None else load_system_prompt()

    def analyze_meeting(self, meeting_text: str) -> AnalyzeMeetingResponse:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": meeting_text},
        ]
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return self._complete(messages)
            except (APITimeoutError, TimeoutError) as exc:
                last_exc = exc
                log.warning("LLM timeout attempt=%s", attempt + 1)
            except RateLimitError as exc:
                last_exc = exc
                wait = _retry_after_seconds(exc, attempt)
                log.warning("LLM rate limit attempt=%s wait=%.1fs", attempt + 1, wait)
                if attempt < self.max_retries:
                    time.sleep(wait)
                    continue
                raise UpstreamRateLimitError("upstream rate limited") from exc
            except InternalServerError as exc:
                last_exc = exc
                wait = _retry_after_seconds(exc, attempt)
                log.warning("LLM %s attempt=%s wait=%.1fs", exc.status_code, attempt + 1, wait)
                if attempt < self.max_retries:
                    time.sleep(wait)
                    continue
                if exc.status_code == 503:
                    raise UpstreamUnavailableError("upstream model overloaded") from exc
                raise UpstreamServerError("upstream server error") from exc
            except APIStatusError as exc:
                last_exc = exc
                if exc.status_code == 429:
                    wait = _retry_after_seconds(exc, attempt)
                    log.warning("LLM 429 attempt=%s wait=%.1fs", attempt + 1, wait)
                    if attempt < self.max_retries:
                        time.sleep(wait)
                        continue
                    raise UpstreamRateLimitError("upstream rate limited") from exc
                if exc.status_code >= 500:
                    wait = _retry_after_seconds(exc, attempt)
                    log.warning("LLM %s attempt=%s wait=%.1fs", exc.status_code, attempt + 1, wait)
                    if attempt < self.max_retries:
                        time.sleep(wait)
                        continue
                    if exc.status_code == 503:
                        raise UpstreamUnavailableError("upstream model overloaded") from exc
                    raise UpstreamServerError("upstream server error") from exc
                raise
            if attempt < self.max_retries:
                time.sleep(min(2 ** attempt, 8))
        raise UpstreamTimeoutError("upstream timeout") from last_exc

    def _complete(self, messages: list[dict]) -> AnalyzeMeetingResponse:
        try:
            response = self.client.chat.completions.parse(
                model=self.model,
                temperature=0,
                messages=messages,
                response_format=AnalyzeMeetingResponse,
                max_tokens=800,
            )
            parsed = response.choices[0].message.parsed
            if parsed is not None:
                return parsed
            refusal = response.choices[0].message.refusal
            if refusal:
                raise InvalidModelOutputError("model refused the request")
            content = response.choices[0].message.content
            if not content:
                raise InvalidModelOutputError("empty model output")
            return AnalyzeMeetingResponse.model_validate_json(content)
        except APIStatusError as exc:
            if exc.status_code != 400:
                raise
            log.warning("structured parse unsupported; falling back to json_object")
            return self._complete_json_object(messages)
        except ValidationError as exc:
            raise InvalidModelOutputError(str(exc)) from exc

    def _complete_json_object(self, messages: list[dict]) -> AnalyzeMeetingResponse:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=800,
        )
        content = response.choices[0].message.content
        if not content:
            raise InvalidModelOutputError("empty model output")
        try:
            return AnalyzeMeetingResponse.model_validate_json(content)
        except ValidationError as exc:
            raise InvalidModelOutputError(str(exc)) from exc
