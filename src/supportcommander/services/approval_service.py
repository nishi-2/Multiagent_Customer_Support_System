from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from supportcommander.db.mongo import (
    get_database,
)


class ApprovalError(Exception):
    """Approval operation failed."""


def record_structured_decision(
    *,
    workflow_id: str,
    decision: str,   # "approved", "modified", or "rejected"
    decided_by: str,
    reason: str,
    commitments: list[str] | None = None,
    next_step: str | None = None,
    modified_actions: list[dict] | None = None,
) -> dict:
    db = get_database()
    # "approved" and "modified" both set status="approved"; "rejected" sets "rejected"
    status = "rejected" if decision == "rejected" else "approved"
    event_type = f"approval_{decision}"

    update_fields = {
        "approval.status": status,
        "approval.decision_type": decision,
        "approval.decided_by": decided_by,
        "approval.decision_reason": reason,
    }
    if commitments:
        update_fields["approval.commitments"] = commitments
    if next_step:
        update_fields["approval.next_step"] = next_step
    if modified_actions:
        update_fields["approval.modified_actions"] = modified_actions

    matched = db.workflows.find_one_and_update(
        {"workflow_id": workflow_id, "approval.status": "pending"},
        {
            "$set": update_fields,
            "$push": {
                "audit_events": {
                    "event_type": event_type,
                    "actor": decided_by,
                    "message": f"Approval {decision} by {decided_by}.",
                    "metadata": {"reason": reason, "decision": decision},
                    "timestamp": datetime.now(timezone.utc),
                }
            },
        },
    )

    if matched is None:
        existing = db.workflows.find_one({"workflow_id": workflow_id}, {"_id": 0, "approval": 1})
        if existing is None:
            raise ApprovalError("Workflow not found.")
        raise ApprovalError("Workflow is not awaiting approval (status is not 'pending').")

    return {"workflow_id": workflow_id, "status": status, "decision": decision}


def record_approval_decision(
    *,
    workflow_id: str,
    approved: bool,
    decided_by: str,
    reason: str,
) -> dict:
    """Backward-compatible binary approve/reject — delegates to record_structured_decision."""
    decision = "approved" if approved else "rejected"
    result = record_structured_decision(
        workflow_id=workflow_id,
        decision=decision,
        decided_by=decided_by,
        reason=reason,
    )
    # Return legacy shape (no "decision" key)
    return {"workflow_id": result["workflow_id"], "status": result["status"]}
