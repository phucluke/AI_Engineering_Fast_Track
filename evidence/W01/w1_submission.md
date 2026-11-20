# Weekly Submission – W1 / Phuc Nguyen

**Feature (F01–F04 or Foundation):** Foundation. Issue classification only. No Jira calls and no API product surface.

**What I studied (2–3 concepts):**
- System and user roles: the system block holds the rules; the user message is only the issue text.
- Few-shot examples and iterative prompt development: V1, V2, and V3 were compared on the same 20 cases and the same model.
- Structured output: every reply is parsed and checked with Pydantic (`category`, `priority`, `next_action`) before it is written to the CSV.

**What I built (summary + key modules):**
- `evidence/W01/prompts.md` — system prompts V1, V2, and V3.
- `app/issue_classifier.py` — loads issue text only, parses JSON, and reads `OPENROUTER_*`.
- `scripts/classify_issues.py` — calls OpenRouter (`openai/gpt-4o-mini`, temperature 0) and writes the scorer CSV.
- `tests/test_issue_classifier.py` — schema, label-stripping, prompt versions, and a dry-run that makes no network call.
- Branch `w1-issue-classifier`. Python 3.12.3. Installed `openai` 2.54.0 and `pydantic` 2.14.4 from `requirements.txt`.

**How to run:**

```bash
python scripts/classify_issues.py --version v3 --output evidence/W01/w1_predictions.csv --details evidence/W01/w1_details.json
python scripts/evaluate_issue_classifier.py evidence/W01/w1_predictions.csv
python scripts/classify_issues.py --version v1 --cases evidence/W01/w1_holdout.json --output evidence/W01/w1_holdout_v1.csv --details evidence/W01/w1_holdout_v1.json
python scripts/classify_issues.py --version v3 --cases evidence/W01/w1_holdout.json --output evidence/W01/w1_holdout_v3.csv --details evidence/W01/w1_holdout_v3.json
pytest -q tests/test_issue_classifier.py
```

Requires `.env` with `OPENROUTER_API_KEY`, `OPENROUTER_MODEL=openai/gpt-4o-mini`, and `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`. `.env` is gitignored.

**Results:**

Public set `data/evaluation/issue_classification_gold.json` (20 cases, course labels, not modified). Model `openai/gpt-4o-mini` via OpenRouter. All 20 replies matched the schema on the first attempt.

| Prompt | Category | Priority | P1 misses |
|---|---|---|---|
| V1 | 20/20 = 100% | 15/20 = 75% | CASE-16 |
| V3 | 20/20 = 100% | 20/20 = 100% | none |

V1 priority misses on the public set: CASE-05, CASE-06, CASE-08 predicted P2 (gold P3); CASE-12 predicted P3 (gold P2); CASE-16 predicted P2 (gold P1).

Holdout `evidence/W01/w1_holdout.json` (10 cases). Labels were written before this run and were not used to edit V3. The course scorer does not read this file. Schema 10/10 on the first attempt for both prompts.

| Prompt | Category | Priority | P1 misses |
|---|---|---|---|
| V1 | 10/10 | 6/10 | H-08 |
| V3 | 10/10 | 9/10 | none |

V3 holdout miss: H-04, "Put the open-blocker count into the Friday delivery note", predicted Feature P3; the holdout label is Feature P2.

Local tests: `pytest -q tests/test_issue_classifier.py` → 6 passed. Existing mock Jira tests were not part of this change.

Security: the user message does not contain gold `category` or `priority` (`test_public_cases_drop_gold_labels`). Invalid category, priority, and empty `next_action` fail validation. No write endpoint is called. `.env` is not committed. This week has no project-access or approval flow; those start in later weeks.

Example: CASE-14 text "Security certificate expires before go-live" → V3 `Risk` / `P1`, next action from `evidence/W01/w1_details.json`.

**Known failures / trade-offs:**
- V3 was tightened after seeing the public gold labels. Several few-shot lines paraphrase those situations, so 20/20 on the public file is not an independent measurement. The holdout is the check that was not used for tuning.
- V3 still missed H-04: a delivery-note change was treated as a small feature (P3) rather than an operating-report change (P2). The priority rule is narrower than the wording in real tickets.
- JSON mode plus one repair call is the schema strategy. Week 2 replaces this with OpenAI structured outputs. Temperature 0 reduces, but does not remove, run-to-run drift.
- One thing that worked: stating that a missing fallback is P1 even when nothing is broken yet. V1 missed that pattern on CASE-16 and H-08; V3 caught both.
- One thing that failed: priority between P2 and P3 for features is still sensitive to phrasing, as H-04 shows.

**Demo link:** Not recorded yet.

**PR link:** Branch: `w1-issue-classifier`.

**Next action:**
