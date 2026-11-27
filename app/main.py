"""Week 2 Meeting Notes API. OpenAI-compatible LLM behind POST /analyze-meeting."""
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from app.schemas import AnalyzeMeetingResponse, MeetingNotesRequest
from app.services.llm import (
    InvalidModelOutputError, LLMService, UpstreamRateLimitError,
    UpstreamServerError, UpstreamTimeoutError, UpstreamUnavailableError,
)

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

app = FastAPI(title="Meeting Notes API", version="0.1")
_llm: LLMService | None = None

class _LazyLLM:
    """Defer LLM client creation until a valid request is handled."""
    def analyze_meeting(self, meeting_text: str) -> AnalyzeMeetingResponse:
        global _llm
        if _llm is None:
            _llm = LLMService()
        return _llm.analyze_meeting(meeting_text)

def get_llm_service() -> Any:
    return _LazyLLM()

@app.post("/analyze-meeting", response_model=AnalyzeMeetingResponse)
def analyze_meeting(
    body: MeetingNotesRequest,
    llm: Any = Depends(get_llm_service),
) -> AnalyzeMeetingResponse:
    try:
        return llm.analyze_meeting(body.meeting_text)
    except UpstreamTimeoutError as exc:
        raise HTTPException(status_code=504, detail="upstream timeout") from exc
    except UpstreamRateLimitError as exc:
        raise HTTPException(status_code=429, detail="upstream rate limited") from exc
    except UpstreamUnavailableError as exc:
        raise HTTPException(status_code=503, detail="upstream model overloaded") from exc
    except UpstreamServerError as exc:
        raise HTTPException(status_code=502, detail="upstream server error") from exc
    except InvalidModelOutputError as exc:
        raise HTTPException(status_code=502, detail="invalid model output") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="LLM settings missing; check .env") from exc
