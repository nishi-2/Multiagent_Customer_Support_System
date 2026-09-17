from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel


POLICY_DIR = Path(__file__).resolve().parents[3] / "data" / "policies"


class PolicyDocument(BaseModel):
    policy_id: str
    title: str
    version: str
    category: str
    content: str
    source_path: str


def extract_field(content: str, field_name: str,) -> str:
    pattern = rf"^{field_name}:\s*(.+)$"
    match = re.search(pattern,content,flags=re.MULTILINE)

    if match is None:
        raise ValueError(f"Missing policy metadata: {field_name}")

    return match.group(1).strip()


def extract_title(content: str,) -> str:
    for line in content.splitlines():
        line = line.strip()

        if line.startswith("# "):
            return line[2:].strip()

    raise ValueError("Policy title not found.")


def load_policy(path: Path,) -> PolicyDocument:
    content = path.read_text(encoding="utf-8")

    return PolicyDocument(
        policy_id=extract_field(content,"Policy ID"),
        title=extract_title(content),
        version=extract_field(content,"Version"),
        category=extract_field(content,"Category"),
        content=content,
        source_path=str(path),
    )


def load_all_policies() -> list[PolicyDocument]:
    paths = sorted(POLICY_DIR.glob("*.md"))

    if not paths:
        raise FileNotFoundError(f"No policies found in {POLICY_DIR}")

    return [load_policy(path) for path in paths]