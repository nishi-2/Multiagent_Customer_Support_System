import pytest

from supportcommander.rag.retriever import retrieve_for_intent


@pytest.mark.asyncio
async def test_refund_policy_retrieval():

    results = await retrieve_for_intent("Customer requests a 450 USD refund for a delivered product.", intent="refund_request", top_k=5)

    assert results

    categories = {result.category for result in results}

    assert categories.issubset({"Refund", "Risk", "Escalation"})

    policy_ids = {result.policy_id for result in results}

    assert "POL-REFUND-001" in policy_ids or "POL-ESCALATE-001" in policy_ids