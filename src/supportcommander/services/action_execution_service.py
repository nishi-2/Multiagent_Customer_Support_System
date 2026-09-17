from __future__ import annotations

from supportcommander.graph.models import (
    ToolExecutionResult,
)
from supportcommander.graph.state import (
    SupportGraphState,
)
from supportcommander.mcp_client.support_client import (
    cancel_order,
    create_replacement,
    issue_refund,
)


def get_execution_context(
    state: SupportGraphState,
) -> tuple[str, str]:

    context = state[
        "customer_context"
    ]

    customer = (
        context.customer
        or {}
    )

    order = (
        context.order
        or {}
    )

    customer_id = customer.get(
        "customer_id"
    )

    order_id = order.get(
        "order_id"
    )

    if not customer_id:
        raise RuntimeError(
            "Customer ID missing."
        )

    if not order_id:
        raise RuntimeError(
            "Order ID missing."
        )

    return (
        customer_id,
        order_id,
    )


TRANSACTIONAL_ACTIONS = {"refund", "replacement", "cancel_order"}


async def execute_action(
    *,
    state: SupportGraphState,
    action,
) -> ToolExecutionResult:

    if action.action_type not in TRANSACTIONAL_ACTIONS:
        return ToolExecutionResult(
            tool_name="none",
            success=True,
            action_type=action.action_type,
            data={"message": "No backend transaction required."},
        )

    customer_id, order_id = (
        get_execution_context(
            state
        )
    )

    if action.action_type == "refund":

        if action.amount is None:
            raise RuntimeError(
                "Refund amount missing."
            )

        result = await issue_refund(
            order_id=order_id,
            customer_id=customer_id,
            amount=action.amount,
            reason=action.reason,
        )

        return ToolExecutionResult(
            tool_name="issue_refund",
            success=result[
                "success"
            ],
            action_type="refund",
            data=result.get(
                "data"
            ),
            error=result.get(
                "error"
            ),
        )

    if (
        action.action_type
        == "replacement"
    ):

        result = (
            await create_replacement(
                order_id=order_id,
                customer_id=customer_id,
                reason=action.reason,
            )
        )

        return ToolExecutionResult(
            tool_name=(
                "create_replacement"
            ),
            success=result[
                "success"
            ],
            action_type="replacement",
            data=result.get(
                "data"
            ),
            error=result.get(
                "error"
            ),
        )

    if (
        action.action_type
        == "cancel_order"
    ):

        result = await cancel_order(
            order_id=order_id,
            customer_id=customer_id,
            reason=action.reason,
        )

        return ToolExecutionResult(
            tool_name="cancel_order",
            success=result[
                "success"
            ],
            action_type="cancel_order",
            data=result.get(
                "data"
            ),
            error=result.get(
                "error"
            ),
        )

    raise RuntimeError(
        f"Unknown transactional action type: {action.action_type}"
    )


async def execute_resolution_plan(
    state: SupportGraphState,
) -> list[
    ToolExecutionResult
]:

    plan = state.get(
        "resolution_plan"
    )

    gate = state.get(
        "policy_gate_result"
    )

    if plan is None:
        raise RuntimeError(
            "Resolution plan missing."
        )

    if gate is None:
        raise RuntimeError(
            "Policy gate result missing."
        )

    allowed = False

    if gate.decision == "allow":
        allowed = True

    elif (
        gate.decision
        in {
            "require_approval",
            "escalate",
        }
    ):
        approval = state.get(
            "approval"
        )

        allowed = (
            approval is not None
            and approval.status
            == "approved"
        )

    if not allowed:
        raise RuntimeError(
            "Transaction execution "
            "is not authorized."
        )

    results = []

    for action in plan.actions:

        if action.action_type == "escalate":
            continue

        result = await execute_action(
            state=state,
            action=action,
        )

        results.append(
            result
        )

    return results
