from __future__ import annotations

from supportcommander.graph.audit import append_audit_event
from supportcommander.graph.models import WorkflowStage
from supportcommander.graph.state import SupportGraphState


def escalate_workflow(state: SupportGraphState, *, reason: str, actor: str) -> None:
    state["escalated"] = True
    state["escalation_reason"] = reason
    state["current_stage"] = WorkflowStage.ESCALATED
    state["next_stage"] = None
    append_audit_event(
        state,
        event_type="workflow_escalated",
        actor=actor,
        message=reason,
    )