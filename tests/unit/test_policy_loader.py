from supportcommander.rag.policy_loader import load_all_policies


def test_policy_loader_returns_policies():
    policies = load_all_policies()
    assert len(policies) >= 6


def test_policy_ids_are_unique():
    policies = load_all_policies()

    ids = [policy.policy_id for policy in policies]
    assert len(ids) == len(set(ids))


def test_refund_policy_exists():
    policies = load_all_policies()
    ids = {policy.policy_id for policy in policies}

    assert "POL-REFUND-001" in ids