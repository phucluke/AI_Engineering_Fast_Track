# AI Engineering Fast-Track V12 – Member Starter Kit

Companion to `TMA_AI_Engineering_Fast_Track_Member_Package_v12_Self_Learning_Ready.pptx`.
This kit provides **real synthetic fixtures and reusable local tools**; it intentionally does **not** include completed assignment solutions.

## Quick start (macOS / Linux / Windows PowerShell equivalent)
1. Install **Python 3.11+**, Git and Docker; use an isolated training environment.
2. `python -m venv .venv` then activate the environment.
3. `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and set `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` (OpenAI SDK; point `BASE_URL` at OpenAI or OpenRouter).
5. `python scripts/smoke_test.py` — expected output ends with **PASS**.
6. `pytest -q tests/test_mock_jira.py` — expected **3 passed**.
7. `uvicorn app.mock_jira:app --reload --port 8001`; visit `http://127.0.0.1:8001/docs`.
8. Example read-only call: `curl -H 'X-Allowed-Project: ALPHA' http://127.0.0.1:8001/projects/ALPHA/sprints/12/issues`.
9. For W3, run `docker compose up -d db` and use pgvector. Your implementation should add the ingestion pipeline.

### Week 2 – Meeting Notes API (Gate 1)
1. `uvicorn app.main:app --reload --port 8000`; OpenAPI at `http://127.0.0.1:8000/docs`.
2. Example: `curl -X POST http://127.0.0.1:8000/analyze-meeting -H "Content-Type: application/json" -d "{\"meeting_text\":\"Meeting Date: 2026-11-23\\nAttendees: Phu\\n\\nPhu will fix login by November 25, 2026.\"}"`.
3. `pytest -q tests/test_meeting_api.py` — error-path and schema tests (no network).
4. `python scripts/evaluate_meeting_notes.py` — scores the 20 public cases in `data/evaluation/week2_meeting_notes_expected_20_cases.json` via the OpenAI-compatible client. Writes `evidence/W02/w2_meeting_results.json`.

Contract: request `{"meeting_text":"..."}`; response `summary`, `decisions`, `actions` (`owner` / `action` / `due_date`, nullable). Switch provider by changing only `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` in `.env`.

### Resource map
- `data/documents/`: 15 synthetic documents plus manifest (5 requirements, 5 technical, 5 PM); plus optional Week 2 companion markdown for meeting-notes cases
- `data/jira/issues.json`: 30 sample issue records for Projects ALPHA/BETA/GAMMA
- `data/evaluation/`: 20 labeled issue cases, 20 meeting-notes cases, 20 retrieval queries, 30 RAG cases, 20 agent scenarios, 10 security cases
- `app/main.py`: Week 2 Meeting Notes API (`POST /analyze-meeting`)
- `app/mock_jira.py`: working read-only mock Jira API for W5 onward
- `scripts/evaluate_issue_classifier.py`: scoring harness; supply CSV with headers `issue_id,predicted_category,predicted_priority`
- `scripts/evaluate_meeting_notes.py`: Week 2 fact/action scorer
- `evidence/weekly_pr_template.md`: required PR/evidence structure
- `assignments/`: weekly handoff instructions; slide deck contains full requirements and PASS criteria

## Safety and limitations
- **TRAINING FIXTURES ONLY.** Do not copy real customer data into model APIs without written approval.
- Mock authorization via `X-Allowed-Project` is **not suitable for production**. Replace with identity, authentication and server-side authorization in W7.
- LLM responses are nondeterministic; test using consistent model configuration, recorded prompt versions and human-reviewed evaluations.
- Hidden mentor assessment fixtures must remain **separate from this member-facing kit**.
- The `requirements.txt` pins broad compatible release families; AI Lead should lock tested versions before program rollout.
- No company-specific Git URL, API credentials, staging URLs or mentor contacts are invented. AI Lead must fill those in during kickoff.
