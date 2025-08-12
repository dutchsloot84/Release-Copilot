import re
from typing import List

JIRA_KEY_RX = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

def extract_keys(text: str) -> List[str]:
    if not text:
        return []
    seen: List[str] = []
    for m in JIRA_KEY_RX.finditer(text):
        key = m.group(1)
        if key not in seen:
            seen.append(key)
    return seen
