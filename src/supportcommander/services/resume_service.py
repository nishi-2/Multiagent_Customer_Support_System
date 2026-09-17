from __future__ import annotations

from supportcommander.agents.response_agent import (
    run_response_agent,
)
from supportcommander.db.mongo import get_database
from supportcommander.graph.models import (
    WorkflowStage,
)
from supportcommander.graph.state_loader import (
    hydrate_workflow_state,
)
from supportcommander.services.action_execution_service import (
    execute_resolution_plan,
)
from supportcommander.services.verification_service import (
    verify_tool_results,
)
from supportcommander.services.workflow_service import (
    get_workflow_state,
    save_workflow_state,
)
from supportcommander.services import cost_tracker, cost_logger


async def resume_workflow(
    workflow_id: str,
) -> dict:

    db = get_database()

    # Atomic execution lock: only one caller can claim the lock.
    # Guards against duplicate tool execution if resume is called twice.
    claimed = db.workflows.find_one_and_update(
        {
            "workflow_id": workflow_id,
            "execution_locked": {"$ne": True},
        },
        {"$set": {"execution_locked": True}},
    )

    if claimed is None:
        existing = db.workflows.find_one(
            {"workflow_id": workflow_id},
            {"_id": 0, "workflow_id": 1},
        )
        if existing is None:
            raise RuntimeError("Workflow not found.")
        raise RuntimeError(
            "Workflow is already executing or was already executed."
        )

    try:
        document = get_workflow_state(workflow_id)

        if document is None:
            raise RuntimeError("Workflow not found.")

        state = hydrate_workflow_state(document)

        # Use explicit None/empty check — `[]` is falsy but means "tried, got nothing"
        if state.get("tool_results") is not None and len(state["tool_results"]) > 0:
            raise RuntimeError(
                "Workflow actions were already executed."
            )

        approval = state.get("approval")

        if approval is None:
            raise RuntimeError("Workflow has no approval state.")

        _acc = cost_tracker.start(
            workflow_id=document["workflow_id"],
            ticket_id=document.get("ticket_id", "unknown"),
            user=document.get("ticket", {}).get("customer_id") or document["workflow_id"],
        )

        try:
            decision_type = getattr(approval, "decision_type", None) or (
                "rejected" if approval.status == "rejected" else "approved"
            )

            if decision_type == "rejected":
                state = await run_response_agent(state)
                state["current_stage"] = WorkflowStage.COMPLETED
                save_workflow_state(state)
                return state

            if approval.status != "approved":
                raise RuntimeError("Workflow approval is still pending.")

            # For "modified": apply any modified_actions to the resolution plan
            if decision_type == "modified":
                modified = getattr(approval, "modified_actions", []) or []
                if modified and state.get("resolution_plan"):
                    plan = state["resolution_plan"]
                    for override in modified:
                        idx = override.get("action_index")
                        if idx is not None and 0 <= idx < len(plan.actions):
                            action = plan.actions[idx]
                            if "amount" in override:
                                action.amount = override["amount"]
                            if "reason" in override:
                                action.reason = override["reason"]

            results = await execute_resolution_plan(state)

            state["tool_results"] = results
            state["current_stage"] = WorkflowStage.ACTION_EXECUTION

            verified = verify_tool_results(state)

            if not verified:
                state["current_stage"] = WorkflowStage.FAILED
                state["next_stage"] = None
                state["error"] = "Transaction verification failed."
            else:
                for result in state["tool_results"]:
                    result.verification_passed = True

                state["current_stage"] = WorkflowStage.VERIFICATION
                state["next_stage"] = WorkflowStage.RESPONSE_DRAFTING
                state = await run_response_agent(state)
                state["current_stage"] = WorkflowStage.COMPLETED

            save_workflow_state(state)
            return state
        finally:
            cost_logger.save(cost_tracker.finish(_acc))

    except Exception:
        # Release the lock so the workflow isn't permanently stuck
        db.workflows.update_one(
            {"workflow_id": workflow_id},
            {"$set": {"execution_locked": False}},
        )
        raise
