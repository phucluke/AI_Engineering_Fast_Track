"""Week 1 issue classifier. Calls an OpenAI-compatible API; never sends gold labels."""
from pathlib import Path
from typing import Literal
import json, re
from pydantic import BaseModel, Field, ValidationError
from app.openai_settings import resolve_openai
ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data/evaluation/issue_classification_gold.json"
PROMPTS = ROOT / "evidence" / "W01" / "prompts.md"

class IssueClassification(BaseModel):
    category: Literal["Bug", "Feature", "Question", "Risk"]
    priority: Literal["P1", "P2", "P3"]
    next_action: str = Field(min_length=1)

def load_public_cases(path: Path = GOLD) -> list[dict]:
    """Issue id and text only. Gold category and priority stay on disk."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [{"issue_id": row["issue_id"], "text": row["text"]} for row in rows]

def load_system_prompt(version: str, path: Path = PROMPTS) -> str:
    version = version.lower()
    if version not in {"v1", "v2", "v3"}:
        raise ValueError(f"unknown prompt version: {version}")
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

def build_messages(system: str, issue_text: str) -> list[dict]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": issue_text},
    ]

def parse_classification(raw: str) -> IssueClassification:
    text = (raw or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, finish = text.find("{"), text.rfind("}")
        if start < 0 or finish < start:
            raise ValueError("model reply has no JSON object")
        text = text[start:finish + 1]
    try:
        return IssueClassification.model_validate_json(text)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
