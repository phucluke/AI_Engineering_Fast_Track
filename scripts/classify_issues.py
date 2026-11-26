"""Classify the 20 public issues via an OpenAI-compatible API and write the scorer CSV.

Usage:
  python scripts/classify_issues.py --version v3
  python scripts/evaluate_issue_classifier.py evidence/W01/w1_predictions_v3.csv

Requires OPENAI_API_KEY and OPENAI_MODEL in .env. Sends issue text only.
"""
from pathlib import Path
import argparse, csv, json, sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from openai import APIStatusError, OpenAI
from app.issue_classifier import (
    build_messages, load_public_cases, load_system_prompt, parse_classification, resolve_openai,
)

def complete(client: OpenAI, model: str, messages: list[dict]) -> str:
    kwargs = {"model": model, "temperature": 0, "messages": messages, "max_tokens": 300}
    try:
        response = client.chat.completions.create(**kwargs, response_format={"type": "json_object"})
    except APIStatusError as exc:
        if exc.status_code != 400:
            raise
        response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM returned an empty message")
    return content

def classify_one(client: OpenAI, model: str, system: str, issue_text: str):
    messages = build_messages(system, issue_text)
    raw = complete(client, model, messages)
    try:
        return parse_classification(raw), raw, 1
    except ValueError:
        repair = messages + [{
            "role": "user",
            "content": (
                "That reply failed schema validation. Return one JSON object only, "
                "with keys category (Bug, Feature, Question, or Risk), "
                "priority (P1, P2, or P3), and next_action (one sentence). "
                f"Issue:\n{issue_text}"
            ),
        }]
        raw = complete(client, model, repair)
        return parse_classification(raw), raw, 2

def write_outputs(rows: list[dict], output: Path, details: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["issue_id", "predicted_category", "predicted_priority"])
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "issue_id": row["issue_id"],
                "predicted_category": row["predicted_category"],
                "predicted_priority": row["predicted_priority"],
            })
    details.write_text(json.dumps(rows, indent=2), encoding="utf-8")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify issues with an OpenAI-compatible model")
    parser.add_argument("--version", required=True, choices=["v1", "v2", "v3"])
    parser.add_argument("--cases", type=Path, default=ROOT / "data/evaluation/issue_classification_gold.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--details", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Print the payload shape and do not call the LLM")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    cases = load_public_cases(args.cases)
    system = load_system_prompt(args.version)
    if args.dry_run:
        sample = build_messages(system, cases[0]["text"])
        print(f"prompt={args.version} cases={len(cases)} user_is_text_only={sample[1]['content']==cases[0]['text']}")
        print("dry-run: no OpenAI call")
        return 0
    settings = resolve_openai()
    client = OpenAI(api_key=settings["api_key"], base_url=settings["base_url"], default_headers=settings["default_headers"] or None)
    rows = []
    for case in cases:
        try:
            parsed, raw, attempts = classify_one(client, settings["model"], system, case["text"])
        except APIStatusError as exc:
            print(f"LLM error {exc.status_code}: {exc.message}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"schema failure {case['issue_id']}: {exc}", file=sys.stderr)
            return 1
        rows.append({
            "issue_id": case["issue_id"],
            "predicted_category": parsed.category,
            "predicted_priority": parsed.priority,
            "next_action": parsed.next_action,
            "prompt_version": args.version,
            "model": settings["model"],
            "schema_attempts": attempts,
            "raw": raw,
        })
        print(f"{case['issue_id']} {parsed.category} {parsed.priority}")
    output = args.output or ROOT / "evidence" / "W01" / f"w1_predictions_{args.version}.csv"
    details = args.details or ROOT / "evidence" / "W01" / f"w1_details_{args.version}.json"
    write_outputs(rows, output, details)
    print(f"wrote {output} ({len(rows)} rows) and {details}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
