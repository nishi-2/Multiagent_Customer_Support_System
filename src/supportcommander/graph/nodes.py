from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from supportcommander.agents.context_agent import (
    run_context_agent,
)
from supportcommander.agents.knowledge_agent import (
    run_knowledge_agent,
)
from supportcommander.agents.resolution_planner import (
    run_resolution_planner,
)
from supportcommander.agents.response_agent import (
    run_response_agent,
)
from supportcommander.agents.risk_agent import (
    run_risk_agent,
)
from supportcommander.agents.triage_agent import (
    run_triage_agent,
)
from supportcommander.graph.models import (
    ApprovalState,
    AuditEvent,
    WorkflowStage,
)
from supportcommander.graph.state import (
    SupportGraphState,
)
from supportcommander.policy.policy_gate import (
    run_policy_gate,
)
from supportcommander.services.action_execution_service import (
    execute_resolution_plan,
)
from supportcommander.services.verification_service import (
    verify_tool_results,
)


def extract_new_audit_events(
    original_state: SupportGraphState,
    result_state: SupportGraphState,
) -> list[AuditEvent]:
    original_count = len(
        original_state.get(
            "audit_events"
        )
        or []
    )

    return (
        result_state.get(
            "audit_events"
        )
        or []
    )[original_count:]


async def triage_node(
    state: SupportGraphState,
) -> dict:

    working = deepcopy(state)
    result = await run_triage_agent(
        working
    )

    return {
        "triage":
            result.get("triage"),

        "current_stage":
            result["current_stage"],

        "next_stage":
            result.get("next_stage"),

        "escalated":
            result.get(
                "escalated",
                False,
            ),

        "escalation_reason":
            result.get(
                "escalation_reason"
            ),

        "error":
            result.get("error"),

        "audit_events":
            extract_new_audit_events(
                state,
                result,
            ),
    }


async def context_node(
    state: SupportGraphState,
) -> dict:

    working = deepcopy(state)
    result = await run_context_agent(
        working
    )

    return {
        "customer_context":
            result.get(
                "customer_context"
            ),

        "audit_events":
            extract_new_audit_events(
                state,
                result,
            ),
    }


async def risk_node(
    state: SupportGraphState,
) -> dict:

    working = deepcopy(state)
    result = await run_risk_agent(
        working
    )

    return {
        "risk_assessment":
            result.get(
                "risk_assessment"
            ),

        "audit_events":
            extract_new_audit_events(
                state,
                result,
            ),
    }


async def knowledge_node(
    state: SupportGraphState,
) -> dict:

    working = deepcopy(state)
    result = await run_knowledge_agent(
        working
    )

    return {
        "retrieved_policies":
            result.get(
                "retrieved_policies",
                [],
            ),

        "audit_events":
            extract_new_audit_events(
                state,
                result,
            ),
    }


def startup_dispatch_node(
    state: SupportGraphState,
) -> dict:
    """Pass-through: fans out from START to triage, context, and risk in parallel."""
    return {}


def startup_join_node(
    state: SupportGraphState,
) -> dict:
    """
    Convergence point after triage + context + risk complete in parallel.
    Surfaces escalation and human_triggers from triage for downstream routing.
    """
    triage = state.get("triage")
    human_triggers: list[str] = []
    if triage and hasattr(triage, "human_triggers"):
        human_triggers = triage.human_triggers or []

    return {
        "current_stage": WorkflowStage.PARALLEL_ANALYSIS,
        "audit_events": [
            AuditEvent(
                timestamp=datetime.now(timezone.utc),
                event_type="startup_parallel_completed",
                actor="coordinator",
                message="Triage, context, and risk completed in parallel.",
                metadata={
                    "ticket_id": state.get("ticket_id"),
                    "human_triggers": human_triggers,
                },
            )
        ],
    }


async def resolution_planner_node(
    state: SupportGraphState,
) -> dict:

    working = deepcopy(state)
    result = await run_resolution_planner(
        working
    )

    return {
        "resolution_plan":
            result.get("resolution_plan"),

        "current_stage":
            result.get(
                "current_stage",
                WorkflowStage.RESOLUTION_PLANNING,
            ),

        "next_stage":
            result.get("next_stage"),

        "error":
            result.get("error"),

        "audit_events":
            extract_new_audit_events(
                state,
                result,
            ),
    }


def policy_gate_node(
    state: SupportGraphState,
) -> dict:

    working_state = deepcopy(
        state
    )

    result = run_policy_gate(
        working_state
    )

    return {
        "policy_gate_result":
            result[
                "policy_gate_result"
            ],

        "current_stage":
            result[
                "current_stage"
            ],

        "next_stage":
            result[
                "next_stage"
            ],

        "audit_events":
            extract_new_audit_events(
                state,
                result,
            ),
    }


def approval_node(
    state: SupportGraphState,
) -> dict:

    gate = state["policy_gate_result"]
    reason = "; ".join(gate.reasons)

    # Build a rich agent-to-human handoff message
    ticket = state.get("ticket") or {}
    raw_ctx = state.get("customer_context")
    if raw_ctx is not None and hasattr(raw_ctx, "model_dump"):
        ctx = raw_ctx.model_dump()
    elif isinstance(raw_ctx, dict):
        ctx = raw_ctx
    else:
        ctx = {}
    triage = state.get("triage")
    risk = state.get("risk_assessment")
    plan = state.get("resolution_plan")

    cust = ctx.get("customer") or {}
    order = ctx.get("order") or {}
    payment = ctx.get("payment") or {}
    refund_history = ctx.get("refund_history") or []
    replacement_history = ctx.get("replacement_history") or []
    shipment = ctx.get("shipment") or {}

    customer_name  = cust.get("name")  or ticket.get("customer_name")  or "Unknown"
    customer_email = cust.get("email") or ticket.get("customer_email") or ticket.get("customer_identifier") or ""
    customer_tier  = cust.get("customer_tier") or "—"
    customer_status= cust.get("account_status") or ""
    customer_phone = cust.get("phone") or ticket.get("customer_phone") or ""
    product        = order.get("product") or ticket.get("product_purchased") or ""
    order_id       = order.get("order_id") or ticket.get("order_id") or ""
    order_amount   = order.get("order_amount")
    order_status   = order.get("order_status") or ""
    payment_method = payment.get("payment_method") or ""
    shipment_status= shipment.get("shipment_status") or ""
    risk_level     = risk.risk_level if risk else "unknown"
    ticket_date    = ticket.get("ticket_date") or ""
    ticket_channel = ticket.get("ticket_channel") or "unknown"

    # ── Customer block
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"⚑  HUMAN REVIEW REQUIRED",
        f"   Ticket #{state.get('ticket_id', '?')}  ·  {ticket_date}  ·  {ticket_channel}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "CUSTOMER",
        f"  Name   : {customer_name}",
    ]
    if customer_email:
        lines.append(f"  Email  : {customer_email}")
    if customer_phone:
        lines.append(f"  Phone  : {customer_phone}")
    if customer_tier and customer_tier != "—":
        lines.append(f"  Tier   : {customer_tier}" + (f"  [{customer_status}]" if customer_status else ""))

    # ── Order / product block (only if data exists)
    if product or order_id or shipment_status:
        lines.append("")
        lines.append("ORDER & SHIPMENT")
        if product:
            lines.append(f"  Product  : {product}")
        if order_id:
            amt_str = f"  ${order_amount:.2f}" if order_amount is not None else ""
            lines.append(f"  Order    : {order_id}{amt_str}  [{order_status}]")
        if payment_method:
            lines.append(f"  Payment  : {payment_method}  [{payment.get('payment_status', '')}]")
        if shipment_status:
            lines.append(f"  Shipment : {shipment_status}  via {shipment.get('carrier', '')}  #{shipment.get('tracking_number', '')}")
        if refund_history:
            lines.append(f"  Prior refunds      : {len(refund_history)}")
        if replacement_history:
            lines.append(f"  Prior replacements : {len(replacement_history)}")

    # ── Ticket / issue block
    lines.append("")
    lines.append("CUSTOMER'S ISSUE")
    if triage:
        intent  = getattr(triage, "intent", "")
        urgency = getattr(triage, "urgency", "")
        summary = getattr(triage, "summary", "")
        lines.append(f"  Intent  : {intent}  |  Urgency: {urgency}")
        if summary:
            lines.append(f"  Summary : {summary}")
    ticket_text = ticket.get("ticket_text") or ticket.get("ticket_subject") or ""
    if ticket_text:
        # Show up to first 200 chars
        short = ticket_text[:200].strip() + ("…" if len(ticket_text) > 200 else "")
        lines.append(f"  Message : \"{short}\"")

    # ── Risk / escalation
    lines.append("")
    lines.append("RISK & ESCALATION")
    if risk:
        signals = ", ".join(risk.risk_signals or []) or "none"
        lines.append(f"  Risk level : {risk_level}  (signals: {signals})")
    lines.append(f"  Gate reason: {reason}")

    # ── Agent recommendation
    lines.append("")
    lines.append("AGENT RECOMMENDATION")
    if plan:
        lines.append(f"  {plan.summary}")
        for action in (plan.actions or []):
            atype = getattr(action, "action_type", str(action))
            areason = getattr(action, "reason", "") or ""
            amt = getattr(action, "amount", None)
            amt_str = f"  ${amt:.2f}" if amt is not None else ""
            lines.append(f"  • {atype}{amt_str}  — {areason}")
        if plan.customer_response_strategy:
            lines.append(f"  Strategy : {plan.customer_response_strategy}")

    lines += [
        "",
        "─────────────────────────────────────",
        "Please Approve, Modify, or Reject.",
        "Your decision will trigger the agent's final response to the customer.",
        "─────────────────────────────────────",
    ]

    agent_recommendation = "\n".join(lines)

    approval = ApprovalState(
        required=True,
        status="pending",
        requested_reason=reason,
        agent_recommendation=agent_recommendation,
    )

    return {
        "approval": approval,
        "current_stage": WorkflowStage.APPROVAL,
        "next_stage": None,
    }



async def action_execution_node(
    state: SupportGraphState,
) -> dict:

    try:
        results = (
            await execute_resolution_plan(
                state
            )
        )
    except Exception as exc:
        return {
            "current_stage":
                WorkflowStage.FAILED,

            "next_stage":
                None,

            "error":
                f"Action execution failed: {exc}",
        }

    return {
        "tool_results":
            results,

        "current_stage":
            WorkflowStage.ACTION_EXECUTION,

        "next_stage":
            WorkflowStage.VERIFICATION,
    }


def verification_node(
    state: SupportGraphState,
) -> dict:

    verified = (
        verify_tool_results(
            state
        )
    )

    updated_results = []

    for result in state.get(
        "tool_results",
        [],
    ):
        copied = (
            result.model_copy()
        )

        copied.verification_passed = (
            verified
        )

        updated_results.append(
            copied
        )

    if not verified:
        return {
            "tool_results":
                updated_results,

            "current_stage":
                WorkflowStage.FAILED,

            "next_stage":
                None,

            "error":
                "Action verification failed.",
        }

    return {
        "tool_results":
            updated_results,

        "current_stage":
            WorkflowStage.VERIFICATION,

        "next_stage":
            WorkflowStage.RESPONSE_DRAFTING,
    }


async def response_drafting_node(
    state: SupportGraphState,
) -> dict:

    working = deepcopy(state)
    result = await run_response_agent(working)

    return {
        "final_response":
            result.get("final_response"),

        "current_stage":
            result["current_stage"],

        "next_stage":
            result.get("next_stage"),

        "audit_events":
            extract_new_audit_events(
                state,
                result,
            ),
    }


