from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from supportcommander.graph.models import AuditEvent, WorkflowStage
from supportcommander.graph.state import SupportGraphState


def create_initial_state(*, ticket_id: int, ticket: dict) -> SupportGraphState:
    return SupportGraphState(
        workflow_id=str(uuid4()),
        ticket_id=ticket_id,
        ticket=ticket,
        retrieved_policies=[],
        tool_results=[],
        audit_events=[
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="workflow_started",
                actor="system",
                message="Support workflow started.",
                metadata={"ticket_id": ticket_id},
            )
        ],
        current_stage=WorkflowStage.INITIALIZED,
        next_stage=None,
        escalated=False,
        escalation_reason=None,
        error=None,
    )


