from __future__ import annotations

import asyncio
import logging

from supportcommander.graph.audit import append_audit_event
from supportcommander.graph.state import SupportGraphState
from supportcommander.rag.retriever import retrieve_for_graph, retrieve_kb_docs

logger = logging.getLogger(__name__)


class KnowledgeAgentError(Exception):
    """Policy retrieval agent failed."""


async def run_knowledge_agent(state: SupportGraphState) -> SupportGraphState:

    append_audit_event(
        state,
        event_type="knowledge_started",
        actor="knowledge_agent",
        message="Knowledge Agent started.",
        metadata={"ticket_id": state["ticket_id"]},
    )

    ticket = state.get("ticket")
    triage = state.get("triage")

    if ticket is None:
        raise KnowledgeAgentError("Ticket is missing from state.")
    if triage is None:
        raise KnowledgeAgentError("Triage result is missing.")

    query = ticket.get("ticket_text")
    if not query:
        raise KnowledgeAgentError("Ticket text is missing.")

    # ── Run policy DB and KB retrieval in parallel ────────────────────────────
    policy_result, kb_result = await asyncio.gather(
        retrieve_for_graph(query, intent=triage.intent, top_k=3),
        retrieve_kb_docs(query, top_k=5),
        return_exceptions=True,
    )

    # Degrade gracefully — one source failing should not kill the agent
    policies: list = []
    kb_docs: list = []

    if isinstance(policy_result, Exception):
        logger.warning("Policy DB retrieval failed: %s", policy_result)
    else:
        policies = policy_result

    if isinstance(kb_result, Exception):
        logger.warning("KB doc retrieval failed: %s", kb_result)
    else:
        kb_docs = kb_result

    # ── Merge and rank by relevance score ─────────────────────────────────────
    merged = policies + kb_docs
    merged.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)

    state["retrieved_policies"] = merged

    # ── Audit ─────────────────────────────────────────────────────────────────
    policy_ids = [
        p.policy_id for p in policies
    ]
    kb_files = list({
        p.citation for p in kb_docs if p.citation
    })

    append_audit_event(
        state,
        event_type="knowledge_completed",
        actor="knowledge_agent",
        message=(
            f"Knowledge Agent completed. "
            f"{len(policies)} policy match(es), "
            f"{len(kb_docs)} KB doc match(es)."
        ),
        metadata={
            "intent":             triage.intent,
            "policy_count":       len(policies),
            "kb_doc_count":       len(kb_docs),
            "policy_ids":         policy_ids,
            "kb_files_cited":     kb_files,
            "total_retrieved":    len(merged),
        },
    )

    return state
