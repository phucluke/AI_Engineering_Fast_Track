from pathlib import Path
import json
p=Path(__file__).resolve().parents[1]
# RAG corpus only: exclude Week 2 evaluation companion docs under data/documents/
docs=[x for x in list((p/'data/documents').glob('*.md'))+list((p/'data/documents').glob('*.txt')) if not x.name.startswith('week2_')]
meeting_cases=p/'data/evaluation/week2_meeting_notes_expected_20_cases.json'
checks={'documents':len(docs),
'jira_issues':len(json.loads((p/'data/jira/issues.json').read_text())),
'issue_cases':len(json.loads((p/'data/evaluation/issue_classification_gold.json').read_text())),
'retrieval_cases':len(json.loads((p/'data/evaluation/retrieval_gold.json').read_text())),
'rag_cases':len(json.loads((p/'data/evaluation/rag_gold.json').read_text())),
'agent_cases':len(json.loads((p/'data/evaluation/agent_cases.json').read_text())),
'security_cases':len(json.loads((p/'data/evaluation/security_cases.json').read_text())),
'meeting_notes_cases':len(json.loads(meeting_cases.read_text())) if meeting_cases.exists() else 0}
for k,n in checks.items(): print(f'{k:18s} {n}')
assert checks=={'documents':15,'jira_issues':30,'issue_cases':20,'retrieval_cases':20,'rag_cases':30,'agent_cases':20,'security_cases':10,'meeting_notes_cases':20}
print('PASS - fixture files and counts are consistent')
