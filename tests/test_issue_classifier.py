"""Week 1 classifier tests. No network calls."""
import json
import pytest
from app.issue_classifier import (
    GOLD, PROMPTS, IssueClassification, build_messages, load_public_cases,
    load_system_prompt, parse_classification, resolve_openrouter,
)

def test_public_cases_drop_gold_labels():
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    cases = load_public_cases()
    assert len(cases) == 20
    assert [row["issue_id"] for row in cases] == [row["issue_id"] for row in gold]
    for case, raw in zip(cases, gold):
        assert set(case) == {"issue_id", "text"}
        assert case["text"] == raw["text"]
        user = build_messages("rules", case["text"])[1]["content"]
        assert user == case["text"]

def test_schema_accepts_valid_and_rejects_bad_values():
    ok = IssueClassification(category="Risk", priority="P1", next_action="Renew the certificate.")
    assert ok.category == "Risk"
    with pytest.raises(ValueError):
        IssueClassification(category="Incident", priority="P1", next_action="Page someone.")
    with pytest.raises(ValueError):
        IssueClassification(category="Bug", priority="P0", next_action="Roll back.")
    with pytest.raises(ValueError):
        IssueClassification(category="Bug", priority="P1", next_action="")

def test_parse_raw_json_and_fenced_json():
    raw = '{"category":"Question","priority":"P3","next_action":"Answer from the release calendar."}'
    assert parse_classification("Note:\n" + raw).priority == "P3"
    fenced = "```json\n" + raw + "\n```"
    assert parse_classification(fenced).category == "Question"
    with pytest.raises(ValueError):
        parse_classification("I think this is a bug, priority high.")
    with pytest.raises(ValueError):
        parse_classification('{"category":"Bug","priority":"P1"}')

def test_three_prompt_versions_and_no_gold_text():
    prompts = {version: load_system_prompt(version) for version in ("v1", "v2", "v3")}
    assert prompts["v1"] != prompts["v2"] != prompts["v3"]
    for prompt in prompts.values():
        for label in ("Bug", "Feature", "Question", "Risk", "P1", "P2", "P3", "next_action"):
            assert label in prompt
    blob = PROMPTS.read_text(encoding="utf-8")
    for row in json.loads(GOLD.read_text(encoding="utf-8")):
        assert row["text"] not in blob

def test_openrouter_settings_ignore_openai_key():
    settings = resolve_openrouter({
        "OPENROUTER_API_KEY": "sk-or-test",
        "OPENROUTER_MODEL": "openai/gpt-4o-mini",
        "OPENAI_API_KEY": "sk-should-not-be-used",
        "OPENROUTER_APP_TITLE": "W1",
    })
    assert settings["api_key"] == "sk-or-test"
    assert settings["base_url"] == "https://openrouter.ai/api/v1"
    assert settings["model"] == "openai/gpt-4o-mini"
    assert settings["default_headers"]["X-Title"] == "W1"
    with pytest.raises(RuntimeError):
        resolve_openrouter({"OPENROUTER_API_KEY": "replace_at_runtime_never_commit", "OPENROUTER_MODEL": "m"})
    with pytest.raises(RuntimeError):
        resolve_openrouter({"OPENROUTER_API_KEY": "sk-or-test", "OPENROUTER_MODEL": ""})

def test_dry_run_makes_no_request(capsys):
    from scripts.classify_issues import main
    assert main(["--version", "v1", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "cases=20" in out
    assert "no OpenRouter call" in out
