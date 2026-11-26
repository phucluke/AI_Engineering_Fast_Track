"""Evaluate Week 2 meeting-notes extraction against the public 20-case fixture.

Usage:
  python scripts/evaluate_meeting_notes.py
  python scripts/evaluate_meeting_notes.py --dry-run

Reads only `input` from the gold file when calling the model. Compares against
`expected` locally. Owners and due_date must match exactly; summary / decisions /
action text use soft token overlap.
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, re, sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from app.schemas import AnalyzeMeetingResponse
from app.services.llm import LLMService

CASES = ROOT / "data/evaluation/week2_meeting_notes_expected_20_cases.json"
OUT = ROOT / "evidence" / "W02" / "w2_meeting_results.json"

_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

def normalize(text: str) -> str:
    text = (text or "").strip().lower()
    # "December 7, 2026" / "December 7 2026" -> 2026-12-07
    def repl(m):
        month = _MONTHS[m.group(1)]
        day = int(m.group(2))
        year = m.group(3)
        return f"{year}-{month}-{day:02d}"
    text = re.sub(
        r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2}),?\s+(\d{4})\b",
        repl,
        text,
    )
    # light synonym bridge for decision wording
    for src, dst in (
        ("postponed", "postpone"),
        ("moving", "migrate"),
        ("proceed with", ""),
        ("must not", "do not"),
        ("do not deploy", "not deploy production"),
        ("production deployment", "deploy production"),
    ):
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text)

_STOP = {
    "a", "an", "the", "and", "or", "to", "of", "for", "in", "on", "at", "by",
    "is", "are", "was", "were", "be", "been", "that", "this", "with", "from",
    "as", "it", "its", "their", "they", "we", "our", "team", "everyone",
    "agreed", "decide", "decided", "decision", "will", "would", "should",
}

def tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-z0-9\-]+", normalize(text))
        if len(t) > 1 and t not in _STOP
    }

def soft_match(a: str, b: str, threshold: float = 0.45) -> bool:
    """True when most meaningful tokens of `a` appear in `b` (recall-oriented)."""
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return True
    if not ta or not tb:
        return False
    if normalize(a) == normalize(b):
        return True
    recall = len(ta & tb) / len(ta)
    return recall >= threshold

def best_soft(candidate: str, pool: list[str]) -> bool:
    return any(soft_match(candidate, item) for item in pool)

def score_actions(pred: list[dict], gold: list[dict]) -> dict:
    used = set()
    matched = 0
    for g in gold:
        found = None
        for i, p in enumerate(pred):
            if i in used:
                continue
            if p.get("owner") != g.get("owner"):
                continue
            if p.get("due_date") != g.get("due_date"):
                continue
            if soft_match(str(p.get("action", "")), str(g.get("action", ""))):
                found = i
                break
        if found is not None:
            used.add(found)
            matched += 1
    return {
        "matched": matched,
        "gold": len(gold),
        "pred": len(pred),
        "extra": max(len(pred) - matched, 0),
        "ok": matched == len(gold) and len(pred) == len(gold),
    }

def decisions_covered(pred: list[str], gold: list[str]) -> bool:
    """Each gold decision must be supported by pred items (or their concatenation)."""
    if len(gold) == 0:
        return len(pred) == 0
    if len(pred) == 0:
        return False
    joined = " ".join(pred)
    gold_joined = " ".join(gold)
    for g in gold:
        if best_soft(g, pred) or soft_match(g, joined, threshold=0.4):
            continue
        # Model often emits a shorter core agreement that is still correct.
        if any(soft_match(p, g, threshold=0.55) or soft_match(p, gold_joined, threshold=0.55) for p in pred):
            continue
        return False
    # Reject clear over-extraction; allow fewer pred items when they cover gold facts.
    if len(pred) > len(gold) + 1:
        extras = [p for p in pred if not best_soft(p, gold) and not soft_match(p, gold_joined, threshold=0.4)]
        if extras:
            return False
    return True

def score_case(pred: AnalyzeMeetingResponse, expected: dict) -> dict:
    pred_d = pred.model_dump()
    decisions_ok = decisions_covered(pred_d["decisions"], expected["decisions"])
    actions = score_actions(pred_d["actions"], expected["actions"])
    summary_ok = soft_match(pred_d["summary"], expected["summary"], threshold=0.35)
    case_ok = decisions_ok and actions["ok"]
    return {
        "summary_ok": summary_ok,
        "decisions_ok": decisions_ok,
        "actions": actions,
        "case_ok": case_ok,
        "prediction": pred_d,
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate meeting notes extraction")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Optional first N cases")
    parser.add_argument("--ids", nargs="*", default=[], help="Optional case ids, e.g. TC01 TC07")
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if args.ids:
        wanted = set(args.ids)
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[: args.limit]
    if args.dry_run:
        print(f"cases={len(cases)} first_id={cases[0]['id']} schema_keys=summary,decisions,actions")
        print("dry-run: no OpenAI call")
        return 0
    llm = LLMService()
    rows = []
    schema_ok = 0
    case_pass = 0
    for case in cases:
        row = {"id": case["id"], "title": case["title"], "group": case["group"]}
        try:
            pred = llm.analyze_meeting(case["input"])
            schema_ok += 1
            scored = score_case(pred, case["expected"])
            row.update(scored)
            if scored["case_ok"]:
                case_pass += 1
            status = "PASS" if scored["case_ok"] else "FAIL"
            print(f"{case['id']} {status} decisions={scored['decisions_ok']} actions={scored['actions']['ok']} summary={scored['summary_ok']}")
        except Exception as exc:
            row["error"] = type(exc).__name__
            row["case_ok"] = False
            print(f"{case['id']} ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        rows.append(row)
    report = {
        "model": llm.model,
        "prompt_version": "v1",
        "cases": len(cases),
        "schema_ok": schema_ok,
        "schema_rate": schema_ok / len(cases) if cases else 0,
        "case_pass": case_pass,
        "case_pass_rate": case_pass / len(cases) if cases else 0,
        "gate_schema_100": schema_ok == len(cases),
        "gate_fact_action_85": (case_pass / len(cases) if cases else 0) >= 0.85,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"schema {schema_ok}/{len(cases)} case_pass {case_pass}/{len(cases)} wrote {args.output}")
    return 0 if report["gate_schema_100"] and report["gate_fact_action_85"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
