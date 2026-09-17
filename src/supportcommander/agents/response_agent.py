from __future__ import annotations

import json

from supportcommander.agents.response_rules import (
    ResponseValidationError,
    validate_final_response,
)
from supportcommander.graph.audit import append_audit_event
from supportcommander.graph.models import FinalResponse, WorkflowStage
from supportcommander.services.llm_service import (
    LLMServiceError,
    generate_text,
)


RESPONSE_INSTRUCTIONS = """
You are the Final Response Agent for SupportCommander, an autonomous customer-support system.

Your task is to write a clear, empathetic, production-quality customer-facing email reply and a brief internal summary.

You receive a JSON object describing the current state of a support workflow, including the customer's name, product, and order details.

Personalization rules (MANDATORY):
1. ALWAYS address the customer by their first name if customer_name is provided (e.g. "Hi Sarah,"). Never use "Dear Customer" or "Hi there".
2. NEVER use placeholders like [Your Name], [Agent Name], [Name], [Team Name], or any bracketed text. Always sign off as "Support Team" or "The Support Team".
3. Reference the specific product by name in the response body.
4. If a refund was processed, state the exact amount from tool_results and confirm it will appear within 3–5 business days.
5. If a replacement was created, confirm it and mention the product name and order ID.
6. If an order was cancelled, confirm the cancellation with the order ID.

Tone and depth rules:
7. Sound like a real, experienced human support agent — warm, direct, and SPECIFIC. No robotic or generic phrasing.
8. Be DESCRIPTIVE and DETAILED about the solution. Walk the customer through what was done or what they should do — don't just say "we've resolved it", explain HOW. If troubleshooting is needed, give concrete numbered steps specific to their product.
9. Never mention internal systems, policy gates, agents, approval workflows, or AI/LLM reasoning.
10. Keep the customer message under 220 words. Use short paragraphs.

Scenario rules:
11. If awaiting human approval (approval_status = "pending"): tell the customer by name that their [specific request] for [product] is under review and they'll hear back within 24 hours. Be specific about what is being reviewed.
12. IMPORTANT — If approval was REJECTED (approval_status = "rejected"): tell the customer by name that after careful review, [specific request] for [product] cannot be fulfilled at this time. Apologise sincerely. If approval_next_step is provided, tell them exactly what will happen next. Set resolution_status to "escalated".
13. If the case was escalated by policy: tell the customer a specialist will personally follow up within 24–48 hours regarding their [product] issue.
14. CONTACT DETAILS — If the customer reports being unable to reach customer support, or asks for a contact number/email, check the retrieved policies/KB for a support phone number, email, or helpline. If found, provide it explicitly in the response. Example: "You can reach our support team directly at 1800-XXX-XXXX (toll-free, Mon–Sat 9 AM–6 PM)." If no number is in the policies, tell the customer to visit the official website's Contact Us page.

Source-awareness rules:
14. GENERAL KNOWLEDGE DISCLAIMER — If knowledge_source = "general", append: "Please note this guidance is based on general best practices. For account-specific details, please don't hesitate to reach out directly."
15. KB DOCUMENT CITATION — If knowledge_source = "company_doc", naturally reference it: "Based on our [document name], ..."
16. HUMAN-APPROVED COMMITMENTS — If approval_status = "approved" and approval_commitments is non-empty, explicitly state what was authorized.
17. MODIFIED APPROVAL — If approval_decision_type = "modified", clearly state what was modified and authorized.
18. REJECTION NEXT STEP — If approval_status = "rejected" and approval_next_step is not null, include that next step verbatim for the customer.

Agent handoff rules (MANDATORY — always generate):
19. ALWAYS generate agent_handoff: a structured internal note to the human support representative.
    Format it EXACTLY as:

    Customer: [Full Name] · [email] · [phone if available, else omit]
    Issue: [one-sentence description of what the customer reported]
    Resolution: [what the agent did or recommended — be specific with amounts, IDs, steps given]
    Status: [Fully resolved autonomously | Pending human approval | Escalated to human | Rejected]
    Human action needed: [exact next step the human must take, OR "None — resolved autonomously"]

    Always include the customer's name and contact details at the top.
    If a refund/replacement/cancellation was executed, state the exact amount and confirmation ID.
    If awaiting approval, state what the human needs to decide and what happens next.
    This note is INTERNAL — NEVER shown to the customer.

Respond ONLY with valid JSON in this exact structure:
{
  "message": "<customer-facing message — no placeholders, sign off as Support Team>",
  "resolution_status": "<resolved|pending_customer|pending_approval|escalated|failed>",
  "action_summary": "<one sentence internal summary>",
  "requires_follow_up": <true|false>,
  "internal_notes": "<optional internal note or null>",
  "agent_handoff": "<mandatory internal note to human representative>"
}
"""


def _classify_knowledge_source(retrieved_policies: list) -> tuple[str, list[str]]:
    """
    Determine the primary knowledge source and any cited KB document names.
    Returns (source_label, kb_docs_cited).
      source_label: "policy_db" | "company_doc" | "general"
    """
    if not retrieved_policies:
        return "general", []

    kb_docs: list[str] = []
    has_policy_db = False

    for p in retrieved_policies:
        source_type = getattr(p, "source_type", "policy_db")
        if source_type == "company_doc":
            citation = getattr(p, "citation", None) or getattr(p, "title", "uploaded document")
            if citation and citation not in kb_docs:
                kb_docs.append(citation)
        else:
            has_policy_db = True

    if kb_docs:
        return "company_doc", kb_docs
    if has_policy_db:
        return "policy_db", []
    return "general", []


def build_response_input(state: dict) -> str:

    triage = state.get("triage")
    plan = state.get("resolution_plan")
    gate = state.get("policy_gate_result")
    approval = state.get("approval")
    tool_results = state.get("tool_results") or []
    ticket = state.get("ticket") or {}
    retrieved_policies = state.get("retrieved_policies") or []
    raw_ctx = state.get("customer_context")
    # customer_context may be a Pydantic model or a dict
    if raw_ctx is not None and hasattr(raw_ctx, "model_dump"):
        customer_context = raw_ctx.model_dump()
    elif isinstance(raw_ctx, dict):
        customer_context = raw_ctx
    else:
        customer_context = {}

    results_data = []
    for r in tool_results:
        results_data.append(
            {
                "action_type": r.action_type,
                "success": r.success,
                "data": r.data,
                "error": r.error,
                "verification_passed": r.verification_passed,
            }
        )

    triage_intent = "unknown"
    if triage is not None:
        triage_intent = getattr(triage, "intent", None) or "unknown"

    knowledge_source, kb_docs_cited = _classify_knowledge_source(retrieved_policies)

    approval_status = approval.status if approval else None

    commitments = []
    next_step_note = None
    decision_type = None
    if approval:
        commitments = getattr(approval, "commitments", []) or []
        next_step_note = getattr(approval, "next_step", None)
        decision_type = getattr(approval, "decision_type", None)

    # Extract customer details from context (enriched) or ticket (raw)
    cust = customer_context.get("customer") or {}
    order = customer_context.get("order") or {}
    payment = customer_context.get("payment") or {}
    refund_history = customer_context.get("refund_history") or []
    replacement_history = customer_context.get("replacement_history") or []

    customer_name = cust.get("name") or ticket.get("customer_name")
    customer_email = cust.get("email") or ticket.get("customer_email")
    customer_tier = cust.get("customer_tier")
    product = order.get("product") or ticket.get("product_purchased")
    order_id = order.get("order_id") or ticket.get("order_id")
    order_amount = order.get("order_amount")
    order_status = order.get("order_status")
    payment_method = payment.get("payment_method")
    purchase_date = order.get("purchase_date") or ticket.get("date_of_purchase")

    payload = {
        # Customer identity — used for personalisation
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_tier": customer_tier,
        # Product & order context
        "product": product,
        "order_id": order_id,
        "order_amount": order_amount,
        "order_status": order_status,
        "payment_method": payment_method,
        "purchase_date": purchase_date,
        "prior_refund_count": len(refund_history),
        "prior_replacement_count": len(replacement_history),
        # Ticket details
        "ticket_subject": ticket.get("ticket_subject", ""),
        "ticket_description": ticket.get("ticket_text", ""),
        # Agent assessment
        "triage_intent": triage_intent,
        "resolution_summary": plan.summary if plan else "",
        "policy_gate_decision": gate.decision if gate else "unknown",
        # Approval
        "approval_status": approval_status,
        "approval_decision_type": decision_type,
        "approval_commitments": commitments,
        "approval_next_step": next_step_note,
        # Actions taken
        "tool_results": results_data,
        "verification_passed": (
            all(r.verification_passed for r in tool_results) if tool_results else False
        ),
        "error": state.get("error"),
        # Source-awareness fields
        "knowledge_source": knowledge_source,
        "kb_docs_cited": kb_docs_cited,
    }

    return json.dumps(payload)


async def run_response_agent(state: dict) -> dict:

    working = dict(state)

    response_input = build_response_input(working)
    _parsed_input = json.loads(response_input)
    _knowledge_source = _parsed_input.get("knowledge_source", "general")
    _kb_docs_cited = _parsed_input.get("kb_docs_cited", [])

    llm_result = await generate_text(
        instructions=RESPONSE_INSTRUCTIONS,
        input_text=response_input,
        _agent_name="response_agent",
    )

    raw_text = llm_result.text.strip()

    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(
            lines[1:-1] if lines[-1].startswith("```") else lines[1:]
        )

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise LLMServiceError(
            f"Response agent returned invalid JSON: {exc}"
        ) from exc

    try:
        final_response = FinalResponse(**data)
    except Exception as exc:
        raise LLMServiceError(
            f"Response agent output failed validation: {exc}"
        ) from exc

    validate_final_response(final_response)

    append_audit_event(
        working,
        event_type="response_drafted",
        actor="response_agent",
        message="Final customer response drafted.",
        metadata={
            "resolution_status": final_response.resolution_status,
            "requires_follow_up": final_response.requires_follow_up,
            "knowledge_source": _knowledge_source,
            "kb_docs_cited": _kb_docs_cited,
        },
    )

    working["final_response"] = final_response
    working["current_stage"] = (
        WorkflowStage.RESPONSE_DRAFTING
    )
    working["next_stage"] = WorkflowStage.COMPLETED

    return working
