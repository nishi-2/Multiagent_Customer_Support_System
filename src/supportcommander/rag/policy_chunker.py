from __future__ import annotations
import re

from supportcommander.rag.models import PolicyChunk
from supportcommander.rag.policy_loader import PolicyDocument


SECTION_PATTERN = re.compile(r"^##\s+(.+)$", flags=re.MULTILINE,)

def split_policy_sections(policy: PolicyDocument) -> list[tuple[str, str]]:
    content = policy.content
    matches = list(SECTION_PATTERN.finditer(content))
    sections = []

    for index, match in enumerate(matches):
        title = (match.group(1).strip())
        start = match.end()

        if (index + 1) < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(content)

        section_content = content[start:end].strip()

        if section_content:
            sections.append((title, section_content))

    return sections


def chunk_policy(policy: PolicyDocument,) -> list[PolicyChunk]:
    sections = split_policy_sections(policy)
    chunks = []

    ignored_sections = {"Purpose"}
    chunk_number = 1

    for section, content in sections:
        if section in ignored_sections:
            continue

        chunk_id = (
            f"{policy.policy_id}"
            f"-CHUNK-{chunk_number:03d}"
        )

        chunk_text = (
            f"Policy: {policy.title}\n"
            f"Policy Category: {policy.category}\n"
            f"Policy Section: {section}\n\n"
            f"{content}"
        )

        chunks.append(
            PolicyChunk(
                chunk_id=chunk_id,
                policy_id=policy.policy_id,
                policy_title=policy.title,
                policy_version=policy.version,
                category=policy.category,
                section=section,
                content=chunk_text,
                source_path=policy.source_path,
            )
        )

        chunk_number += 1
    return chunks


def chunk_policies(policies: list[PolicyDocument]) -> list[PolicyChunk]:
    chunks = []
    for policy in policies:
        chunks.extend(chunk_policy(policy))

    return chunks