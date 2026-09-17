from __future__ import annotations

import asyncio

from supportcommander.graph.audit import append_audit_event
from supportcommander.graph.models import (
    CustomerContext,
)
from supportcommander.graph.state import (
    SupportGraphState,
)
from supportcommander.mcp_client.support_client import (
    SupportMCPError,
    get_customer,
    get_order,
    get_payment,
    get_refund_history,
    get_replacement_history,
    get_shipment,
)


class ContextAgentError(Exception):
    """Customer context collection failed."""


def extract_tool_data(
    result: dict,
    *,
    field_name: str,
    missing_data: list[str],
):
    if not result.get("success"):
        missing_data.append(
            field_name
        )
        return None

    return result.get(
        "data"
    )


async def run_context_agent(
    state: SupportGraphState,
) -> SupportGraphState:

    append_audit_event(
        state,
        event_type="context_started",
        actor="context_agent",
        message="Context Agent started.",
        metadata={
            "ticket_id":
                state["ticket_id"]
        },
    )

    ticket = state.get(
        "ticket"
    )

    if ticket is None:
        raise ContextAgentError(
            "Ticket is missing from state."
        )

    customer_id = ticket.get(
        "customer_id"
    )

    order_id = ticket.get(
        "order_id"
    )

    if not customer_id:
        # User-uploaded tickets have no account data — return empty context
        state["customer_context"] = CustomerContext()
        append_audit_event(
            state,
            event_type="context_completed",
            actor="context_agent",
            message="No customer_id — skipping context lookup.",
            metadata={"ticket_id": state["ticket_id"]},
        )
        return state

    if not order_id:
        raise ContextAgentError(
            "Ticket does not contain order_id."
        )

    missing_data: list[str] = []

    try:
        (
            customer_result,
            order_result,
            payment_result,
            shipment_result,
            refund_result,
            replacement_result,
        ) = await asyncio.gather(
            get_customer(customer_id),
            get_order(order_id),
            get_payment(order_id),
            get_shipment(order_id),
            get_refund_history(customer_id),
            get_replacement_history(customer_id),
        )

    except SupportMCPError as exc:

        append_audit_event(
            state,
            event_type="context_failed",
            actor="context_agent",
            message="Context Agent MCP call failed.",
            metadata={
                "error": str(exc)
            },
        )

        raise ContextAgentError(
            "Context Agent MCP call failed."
        ) from exc

    customer = extract_tool_data(
        customer_result,
        field_name="customer",
        missing_data=missing_data,
    )

    order = extract_tool_data(
        order_result,
        field_name="order",
        missing_data=missing_data,
    )

    payment = extract_tool_data(
        payment_result,
        field_name="payment",
        missing_data=missing_data,
    )

    shipment = extract_tool_data(
        shipment_result,
        field_name="shipment",
        missing_data=missing_data,
    )

    refund_history = (
        extract_tool_data(
            refund_result,
            field_name="refund_history",
            missing_data=missing_data,
        )
        or []
    )

    replacement_history = (
        extract_tool_data(
            replacement_result,
            field_name=(
                "replacement_history"
            ),
            missing_data=missing_data,
        )
        or []
    )

    context = CustomerContext(
        customer=customer,
        order=order,
        payment=payment,
        shipment=shipment,
        refund_history=refund_history,
        replacement_history=(
            replacement_history
        ),
        missing_data=missing_data,
    )

    state[
        "customer_context"
    ] = context

    append_audit_event(
        state,
        event_type="context_completed",
        actor="context_agent",
        message="Context Agent completed.",
        metadata={
            "missing_data":
                missing_data,

            "refund_records":
                len(refund_history),

            "replacement_records":
                len(
                    replacement_history
                ),
        },
    )

    return state
