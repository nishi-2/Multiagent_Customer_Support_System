from supportcommander.rag.policy_loader import load_all_policies


def main() -> None:
    policies = load_all_policies()
    print("=" * 70)
    print("SupportCommander Policy Report")
    print("=" * 70)

    for policy in policies:
        print()
        print(policy.policy_id)
        print(f"Title: {policy.title}")
        print(f"Category: {policy.category}")
        print(f"Version: {policy.version}")
        print(f"Source: {policy.source_path}")

    print()
    print(f"Total policies: {len(policies)}")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()