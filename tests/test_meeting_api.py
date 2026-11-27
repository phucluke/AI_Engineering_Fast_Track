"""Week 2 Meeting Notes API tests. No network calls."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from openai import APIStatusError, APITimeoutError, InternalServerError, RateLimitError
from app.main import app, get_llm_service
from app.schemas import AnalyzeMeetingResponse, MeetingAction
from app.services.llm import LLMService, InvalidModelOutputError

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data/evaluation/week2_meeting_notes_expected_20_cases.json"

class FakeHTTPResponse:
    def __init__(self, status_code: int, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.request = None

def _status_error(code: int, message: str = "upstream") -> APIStatusError:
    return APIStatusError(message, response=FakeHTTPResponse(code), body={"error": message})

def _rate_limit_error(message: str = "slow down") -> RateLimitError:
    return RateLimitError(message, response=FakeHTTPResponse(429), body={"error": message})

def _internal_server_error(code: int, message: str = "boom") -> InternalServerError:
    return InternalServerError(message, response=FakeHTTPResponse(code), body={"error": message})

@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_invalid_payload_returns_422(client):
    assert client.post("/analyze-meeting", json={}).status_code == 422
    assert client.post("/analyze-meeting", json={"meeting_text": ""}).status_code == 422

def test_timeout_returns_504(client):
    class Boom(LLMService):
        def __init__(self):
            pass
        def analyze_meeting(self, meeting_text: str):
            from app.services.llm import UpstreamTimeoutError
            raise UpstreamTimeoutError("upstream timeout")
    app.dependency_overrides[get_llm_service] = lambda: Boom()
    r = client.post("/analyze-meeting", json={"meeting_text": "Meeting Date: 2026-11-23\nNo actions."})
    assert r.status_code == 504
    assert "timeout" in r.json()["detail"]

def test_rate_limit_returns_429(client):
    class Boom(LLMService):
        def __init__(self):
            pass
        def analyze_meeting(self, meeting_text: str):
            from app.services.llm import UpstreamRateLimitError
            raise UpstreamRateLimitError("upstream rate limited")
    app.dependency_overrides[get_llm_service] = lambda: Boom()
    r = client.post("/analyze-meeting", json={"meeting_text": "Meeting Date: 2026-11-23\nNo actions."})
    assert r.status_code == 429
    assert "rate" in r.json()["detail"]

def test_upstream_503_returns_503(client):
    class Boom(LLMService):
        def __init__(self):
            pass
        def analyze_meeting(self, meeting_text: str):
            from app.services.llm import UpstreamUnavailableError
            raise UpstreamUnavailableError("upstream model overloaded")
    app.dependency_overrides[get_llm_service] = lambda: Boom()
    r = client.post("/analyze-meeting", json={"meeting_text": "Meeting Date: 2026-11-23\nNo actions."})
    assert r.status_code == 503
    assert "overloaded" in r.json()["detail"]

def test_upstream_500_returns_502(client):
    class Boom(LLMService):
        def __init__(self):
            pass
        def analyze_meeting(self, meeting_text: str):
            from app.services.llm import UpstreamServerError
            raise UpstreamServerError("upstream server error")
    app.dependency_overrides[get_llm_service] = lambda: Boom()
    r = client.post("/analyze-meeting", json={"meeting_text": "Meeting Date: 2026-11-23\nNo actions."})
    assert r.status_code == 502
    assert "server" in r.json()["detail"]

def test_broken_model_output_returns_502(client):
    class Boom(LLMService):
        def __init__(self):
            pass
        def analyze_meeting(self, meeting_text: str):
            raise InvalidModelOutputError("empty model output")
    app.dependency_overrides[get_llm_service] = lambda: Boom()
    r = client.post("/analyze-meeting", json={"meeting_text": "Meeting Date: 2026-11-23\nNo actions."})
    assert r.status_code == 502
    assert "invalid" in r.json()["detail"]

def test_happy_path_tc06_schema_with_null_due_dates(client):
    gold = next(c for c in json.loads(CASES.read_text(encoding="utf-8")) if c["id"] == "TC06")
    expected = AnalyzeMeetingResponse.model_validate(gold["expected"])
    class Ok(LLMService):
        def __init__(self):
            pass
        def analyze_meeting(self, meeting_text: str):
            assert meeting_text == gold["input"]
            return expected
    app.dependency_overrides[get_llm_service] = lambda: Ok()
    r = client.post("/analyze-meeting", json={"meeting_text": gold["input"]})
    assert r.status_code == 200
    body = r.json()
    assert body["summary"]
    assert body["decisions"] == []
    assert len(body["actions"]) == 2
    assert body["actions"][0]["due_date"] is None
    assert body["actions"][1]["due_date"] is None
    assert "owner" in body["actions"][0]
    assert "action_items" not in body

def test_llm_maps_timeout_after_retries(monkeypatch):
    calls = {"n": 0}
    class FakeClient:
        def __init__(self):
            self.chat = self
            self.completions = self
        def parse(self, **kwargs):
            calls["n"] += 1
            raise APITimeoutError(request=None)
    svc = LLMService(client=FakeClient(), model="test-model", max_retries=1, system_prompt="extract")
    monkeypatch.setattr("app.services.llm.time.sleep", lambda *_: None)
    from app.services.llm import UpstreamTimeoutError
    with pytest.raises(UpstreamTimeoutError):
        svc.analyze_meeting("notes")
    assert calls["n"] == 2

def test_llm_maps_rate_limit_error(monkeypatch):
    monkeypatch.setattr("app.services.llm.time.sleep", lambda *_: None)
    class RateClient:
        def __init__(self):
            self.chat = self
            self.completions = self
        def parse(self, **kwargs):
            raise _rate_limit_error()
    from app.services.llm import UpstreamRateLimitError
    svc = LLMService(client=RateClient(), model="m", max_retries=0, system_prompt="x")
    with pytest.raises(UpstreamRateLimitError):
        svc.analyze_meeting("notes")

def test_llm_maps_429_api_status_fallback(monkeypatch):
    monkeypatch.setattr("app.services.llm.time.sleep", lambda *_: None)
    class RateClient:
        def __init__(self):
            self.chat = self
            self.completions = self
        def parse(self, **kwargs):
            raise _status_error(429, "slow down")
    from app.services.llm import UpstreamRateLimitError
    svc = LLMService(client=RateClient(), model="m", max_retries=0, system_prompt="x")
    with pytest.raises(UpstreamRateLimitError):
        svc.analyze_meeting("notes")

def test_llm_maps_internal_server_errors(monkeypatch):
    monkeypatch.setattr("app.services.llm.time.sleep", lambda *_: None)
    from app.services.llm import UpstreamServerError, UpstreamUnavailableError
    class OverloadedClient:
        def __init__(self):
            self.chat = self
            self.completions = self
        def parse(self, **kwargs):
            raise _internal_server_error(503, "server_is_overloaded")
    svc503 = LLMService(client=OverloadedClient(), model="m", max_retries=0, system_prompt="x")
    with pytest.raises(UpstreamUnavailableError):
        svc503.analyze_meeting("notes")
    class ServerClient:
        def __init__(self):
            self.chat = self
            self.completions = self
        def parse(self, **kwargs):
            raise _internal_server_error(500, "boom")
    svc500 = LLMService(client=ServerClient(), model="m", max_retries=0, system_prompt="x")
    with pytest.raises(UpstreamServerError):
        svc500.analyze_meeting("notes")

def test_llm_invalid_parse_raises(monkeypatch):
    class BadClient:
        def __init__(self):
            self.chat = self
            self.completions = self
        def parse(self, **kwargs):
            class Msg:
                parsed = None
                refusal = None
                content = '{"summary":""}'
            class Choice:
                message = Msg()
            class Resp:
                choices = [Choice()]
            return Resp()
        def create(self, **kwargs):
            class Msg:
                content = '{"summary":""}'
            class Choice:
                message = Msg()
            class Resp:
                choices = [Choice()]
            return Resp()
    svc = LLMService(client=BadClient(), model="m", max_retries=0, system_prompt="x")
    with pytest.raises(InvalidModelOutputError):
        svc.analyze_meeting("notes")

def test_response_schema_accepts_null_owner():
    item = MeetingAction(owner=None, action="Update docs", due_date="2026-11-30")
    assert item.owner is None
    ok = AnalyzeMeetingResponse(summary="Docs need work.", decisions=["Improve docs."], actions=[item])
    assert ok.actions[0].due_date == "2026-11-30"
