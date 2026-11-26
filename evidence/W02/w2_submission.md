# Weekly Submission – W2 / Phuc Nguyen

**Feature (F01–F04 or Foundation):** Foundation / Gate 1. Meeting Notes API only. No Jira calls.

**What I studied (2–3 concepts):**
- OpenAI-compatible structured outputs (`chat.completions.parse` + Pydantic) through OpenRouter.
- Upstream failure handling: timeout, 429 with backoff/`Retry-After`, 5xx, and invalid model JSON mapped to stable HTTP statuses without leaking secrets.
- Extraction rules for nullable `owner` / `due_date`, and treating proposals as non-decisions.

**What I built (summary + key modules):**
- `app/main.py` — FastAPI `POST /analyze-meeting` with OpenAPI docs.
- `app/schemas.py` — request `meeting_text`; response `summary`, `decisions`, `actions`.
- `app/services/llm.py` — OpenRouter client, structured output, retries, error mapping.
- `app/openai_settings.py` — shared `OPENAI_*` resolution (api_key / base_url / model; OpenAI or OpenRouter).
- `tests/test_meeting_api.py` — 5 required error paths + schema happy path (no network).
- `scripts/evaluate_meeting_notes.py` — scores the public 20-case fixture.
- `evidence/W02/system_prompt.md` — extraction system prompt v1.
- Branch `w2-meeting-notes-api`. Current `.env` points OpenAI SDK at OpenRouter (`openai/gpt-4o-mini`).

**How to run:**

```bash
uvicorn app.main:app --reload --port 8000
pytest -q tests/test_meeting_api.py
python scripts/evaluate_meeting_notes.py
python scripts/smoke_test.py
```

Requires `.env` with `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`. Never commit `.env`.

Example request:

```bash
curl -X POST http://127.0.0.1:8000/analyze-meeting -H "Content-Type: application/json" -d "{\"meeting_text\":\"Meeting Date: 2026-11-23\\nAttendees: Phu, Hung, Minh\\n\\nThe team agreed to prioritize the login bug. Phu will fix the login authentication issue by November 25, 2026.\"}"
```

**Results:**

Public set `data/evaluation/week2_meeting_notes_expected_20_cases.json` (20 cases). Companion contract: `data/documents/week2_meeting_notes_expected_20_cases.md`.

| Check | Result |
|---|---|
| Schema on successful calls | 20/20 = 100% |
| Case pass (actions exact owner/due_date + soft decisions) | 20/20 = 100% |
| Gate fact/action ≥ 85% | PASS |
| Local API error tests | `pytest -q tests/test_meeting_api.py` → passed (invalid payload, timeout, 429, upstream 500, broken model output) |
| Smoke | `python scripts/smoke_test.py` → PASS |

Raw predictions and per-case scores: `evidence/W02/w2_meeting_results.json`.

Security: API key only in `.env` (gitignored). `.env.example` uses placeholders. Error responses and logs do not echo the key. This week has no project-access filter.

**Known failures / trade-offs:**
- Soft semantic matching is required for summary/decision wording; owners and ISO dates are exact.
- Structured `parse` may fall back to `json_object` if the provider rejects the schema (logged, still Pydantic-validated).
- One thing that worked: treating “agreed that…” with no assignees as a decision (TC09).
- One remaining risk: nondeterminism across OpenRouter runs; temperature is 0 but wording can still drift.

**Demo link:** Not recorded yet. OpenAPI: `http://127.0.0.1:8000/docs`.

**PR link:** Branch: `w2-meeting-notes-api`.

**Next action:** Week 3 document ingest + pgvector retrieval.
