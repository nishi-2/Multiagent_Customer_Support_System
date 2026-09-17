from supportcommander.rag.retriever import INTENT_POLICY_CATEGORIES


def test_refund_categories():
    assert (INTENT_POLICY_CATEGORIES["refund_request"] == ["Refund", "Risk", "Escalation"])


def test_billing_categories():
    assert "Billing" in INTENT_POLICY_CATEGORIES["billing_inquiry"]


def test_technical_categories():
    assert "Replacement" in INTENT_POLICY_CATEGORIES["technical_issue"]