from __future__ import annotations

from supportcommander.agents.risk_rules import (
    assess_context_risk,
    risk_level_from_score,
)
from supportcommander.graph.audit import append_audit_event
from supportcommander.graph.models import (
    RiskAssessment,
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
)


class RiskAgentError(Exception):
    """Risk assessment failed."""


async def collect_risk_context(
    state: SupportGraphState,
):
    ticket = state.get(
        "ticket"
    )

    if ticket is None:
        raise RiskAgentError(
            "Ticket is missing from state."
        )

    customer_id = ticket.get(
        "customer_id"
    )

    order_id = ticket.get(
        "order_id"
    )

    if not customer_id or not order_id:
        # User-uploaded tickets have no account/order data — return low risk
        return {
            "customer": None,
            "order": None,
            "payment": None,
            "refund_history": [],
            "replacement_history": [],
        }

    try:
        customer = await get_customer(
            customer_id
        )

        order = await get_order(
            order_id
        )

        payment = await get_payment(
            order_id
        )

        refunds = await get_refund_history(
            customer_id
        )

        replacements = (
            await get_replacement_history(
                customer_id
            )
        )

    except SupportMCPError as exc:
        raise RiskAgentError(
            "Risk Agent MCP lookup failed."
        ) from exc

    return {
        "customer":
            customer.get("data")
            if customer.get("success")
            else None,

        "order":
            order.get("data")
            if order.get("success")
            else None,

        "payment":
            payment.get("data")
            if payment.get("success")
            else None,

        "refund_history":
            refunds.get("data")
            if refunds.get("success")
            else [],

        "replacement_history":
            replacements.get("data")
            if replacements.get("success")
            else [],
    }


async def run_risk_agent(
    state: SupportGraphState,
) -> SupportGraphState:

    append_audit_event(
        state,
        event_type="risk_started",
        actor="risk_agent",
        message="Risk Agent started.",
        metadata={
            "ticket_id":
                state["ticket_id"]
        },
    )

    ticket = state.get("ticket", {})
    has_ids = bool(ticket.get("customer_id") or ticket.get("order_id"))

    risk_context = (
        await collect_risk_context(
            state
        )
    )

    if not has_ids:
        # Dataset/uploaded tickets have no backend records — no lookup was
        # attempted, so missing data is expected, not a risk signal.
        score, signals = 0.0, []
    else:
        score, signals = (
            assess_context_risk(
                customer=(
                    risk_context[
                        "customer"
                    ]
                ),
                order=(
                    risk_context[
                        "order"
                    ]
                ),
                payment=(
                    risk_context[
                        "payment"
                    ]
                ),
                refund_history=(
                    risk_context[
                        "refund_history"
                    ]
                ),
                replacement_history=(
                    risk_context[
                        "replacement_history"
                    ]
                ),
            )
        )

    risk_level = (
        risk_level_from_score(
            score
        )
    )

    requires_human_review = (
        risk_level
        in {
            "medium",
            "high",
        }
    )

    if signals:
        rationale = (
            "Risk signals detected: "
            + ", ".join(signals)
        )
    else:
        rationale = (
            "No significant risk signals "
            "were detected."
        )

    assessment = RiskAssessment(
        risk_level=risk_level,
        risk_score=score,
        risk_signals=signals,
        requires_human_review=(
            requires_human_review
        ),
        rationale=rationale,
    )

    state[
        "risk_assessment"
    ] = assessment

    append_audit_event(
        state,
        event_type="risk_completed",
        actor="risk_agent",
        message="Risk Agent completed.",
        metadata={
            "risk_level":
                risk_level,

            "risk_score":
                score,

            "signals":
                signals,

            "requires_human_review":
                requires_human_review,
        },
    )

    return state
