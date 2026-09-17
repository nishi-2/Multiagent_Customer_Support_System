from supportcommander.graph.models import TriageResult


def apply_triage_rules(triage: TriageResult) -> TriageResult:

    # Transactional intents always need customer/order context.
    if triage.intent in {"refund_request", "cancellation_request", "billing_inquiry"}:
        triage.needs_customer_context = True

    # Refund and cancellation decisions require policy evaluation.
    if triage.intent in {"refund_request", "cancellation_request"}:
        triage.needs_policy_lookup = True

    # Financial requests always require risk evaluation.
    if triage.intent in {"refund_request", "billing_inquiry"}:
        triage.needs_risk_review = True

    # Very urgent cases require risk review.
    if triage.urgency in {"high","critical"}:
        triage.needs_risk_review = True

    return triage