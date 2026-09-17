from supportcommander.rag.policy_loader import load_all_policies


EXPECTED_POLICY_IDS = {
    "POL-REFUND-001",
    "POL-CANCEL-001",
    "POL-REPLACE-001",
    "POL-BILLING-001",
    "POL-RISK-001",
    "POL-ESCALATE-001",
}


def main() -> None:

    print("=" * 70)
    print("SupportCommander Policy Check")
    print("=" * 70)

    policies = load_all_policies()

    print(f"Policies loaded: {len(policies)}")

    policy_ids = {policy.policy_id for policy in policies}

    missing = EXPECTED_POLICY_IDS - policy_ids

    if missing:
        raise ValueError(f"Missing policy IDs: {sorted(missing)}")

    if len(policy_ids) != len(policies):
        raise ValueError("Duplicate policy IDs found.")

    for policy in policies:
        print()
        print(  f"{policy.policy_id}")
        print(f"  Title: {policy.title}")
        print(f"  Category: {policy.category}")
        print(f"  Version: {policy.version}")
        print(f"  Characters: {len(policy.content):,}")

    print()
    print("Policy IDs: OK")
    print("Policy metadata: OK")

    print()
    print("=" * 70)
    print("Policy knowledge base successful!")
    print("=" * 70)


if __name__ == "__main__":
    main()