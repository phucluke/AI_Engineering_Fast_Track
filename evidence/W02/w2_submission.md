# Weekly Submission – W2 / Phuc Nguyen

**Feature (F01–F04 or Foundation):** Foundation — **Gate 1**. Meeting Notes API (`POST /analyze-meeting`). Model calls via the OpenAI-compatible SDK; **no** Jira integration and **no** project-level authorization (W7).


**What I studied (2–3 concepts):**

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs): `chat.completions.parse` + a Pydantic response model (replaces W1 JSON mode + repair).
- [Error codes / 429](https://developers.openai.com/api/docs/guides/error-codes): timeout → 504; rate limit → 429 with backoff; separate upstream failures from unparseable model output.
- Extraction rules: nullable `owner` / `due_date`; ISO dates only when explicit in the notes; proposals / “maybe” must not become committed actions.

**What I built (summary + key modules):**

- `app/main.py` — FastAPI, `get_llm_service` dependency, `POST /analyze-meeting`.
- `app/schemas.py` — `MeetingNotesRequest`, `MeetingAction`, `AnalyzeMeetingResponse`.
- `app/services/llm.py` — OpenRouter/OpenAI client, structured parse, 429 retries, exceptions → HTTP.
- `app/openai_settings.py` — `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` (switch provider by editing `.env` only).
- `tests/test_meeting_api.py` — 5 required error paths + happy-path schema (TC06 null dates) + LLM error-mapping units; **no network calls**.
- `scripts/evaluate_meeting_notes.py` — schema + soft match on summary/decisions + exact `owner`/`due_date` on 20 cases.
- `evidence/W02/system_prompt.md` — extraction system prompt v1.
- Branch: `w2-meeting-notes-api`. Current model: `openai/gpt-4o-mini` via OpenRouter (`temperature=0`).

**How to run:**

```bash
uvicorn app.main:app --reload --port 8000
pytest -q tests/test_meeting_api.py
python scripts/evaluate_meeting_notes.py
python scripts/smoke_test.py
```

Requires `.env` (never commit): `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`.

**Example request / response (Gate 1 contract):**

Request:

```json
{
  "meeting_text": "Meeting Date: 2026-11-23\nAttendees: Phu, Hung, Minh\n\nThe team agreed to prioritize the login bug. Phu will fix the login authentication issue by November 25, 2026."
}
```

Response (200, `AnalyzeMeetingResponse` schema):

```json
{
  "summary": "…",
  "decisions": ["agreed to prioritize the login bug"],
  "actions": [
    {
      "owner": "Phu",
      "action": "fix the login authentication issue",
      "due_date": "2026-11-25"
    }
  ]
}
```

```bash
curl -X POST http://127.0.0.1:8000/analyze-meeting -H "Content-Type: application/json" -d "{\"meeting_text\":\"Meeting Date: 2026-11-23\\nAttendees: Phu\\n\\nPhu will fix login by November 25, 2026.\"}"
```

**Results:**

Gold set: `data/evaluation/week2_meeting_notes_expected_20_cases.json` (20 cases). Companion: `data/documents/week2_meeting_notes_expected_20_cases.md`.

### Evaluation (20 public cases)

| Metric | Result |
|--------|--------|
| Schema on successful LLM calls | 20/20 = 100% |
| Case pass (actions: exact owner + `due_date`; decisions: soft match) | 20/20 = 100% |
| Gate fact/action ≥ 85% | PASS |
| Smoke | `python scripts/smoke_test.py` → PASS |

Raw scorer output: `evidence/W02/w2_meeting_results.json` (`prompt_version: v1`, `model: openai/gpt-4o-mini`).

### API negative tests (5 required — `tests/test_meeting_api.py`)

| Scenario | Test | HTTP |
|----------|------|------|
| Invalid payload | `test_invalid_payload_returns_422` | 422 |
| Upstream timeout | `test_timeout_returns_504` | 504 |
| Rate limit 429 | `test_rate_limit_returns_429` | 429 |
| Upstream 500 | `test_upstream_500_returns_502` | 502 |
| Broken model output | `test_broken_model_output_returns_502` | 502 |

Extra (beyond the slide deck, still tested): upstream 503 → 503; unit tests for `LLMService` error mapping (retries, `InvalidModelOutputError`).

Local run: `pytest -q tests/test_meeting_api.py` (expect all passed, no network).

**Security:**

- API key only in `.env` (gitignored); `.env.example` uses placeholders.
- Error responses and logs do not print the key.
- Week 2 has no project filter or cross-project checks (security cases come in later weeks).

**Known failures / trade-offs:**

- Summary and decisions use soft semantic matching; `owner` and `due_date` are exact against gold.
- Some providers reject `parse` with a JSON schema → fallback to `json_object` then Pydantic validation (logged).
- TC09-style: “agreed that …” with no assignee → decision only, no action — must be explicit in the prompt.
- Nondeterminism: `temperature=0` helps but does not eliminate wording drift on re-runs of evaluate.

**Demo link:** Not recorded yet. Local Swagger UI: `http://127.0.0.1:8000` (run uvicorn per README, then open the FastAPI interactive API page).

**PR link:** Branch `w2-meeting-notes-api` (add PR URL after push, using `evidence/weekly_pr_template.md`).

**Next action:** W3 — ingest the 15 synthetic files under `data/documents/`, chunk, embed, pgvector, search API with `project_id` filter before top-k.