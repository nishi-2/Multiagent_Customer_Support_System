import pandas as pd


DATASET_PATH = ("data/processed/support_tickets_clean.csv")

def main() -> None:
    df = pd.read_csv(DATASET_PATH)

    print("=" * 70)
    print("SupportCommander Ticket Lifecycle Validation")
    print("=" * 70)

    for status in ["Open", "Pending Customer Response", "Closed",]:
        subset = df[df["ticket_status"] == status]

        print()
        print(f"Status: {status}")
        print(f"Tickets: {len(subset):,}")

        print("Missing first response:",subset["first_response_time"].isna().sum(),)
        print(
            "Missing resolution time:",
            subset["time_to_resolution"]
            .isna()
            .sum(),
        )

        print(
            "Missing satisfaction rating:",
            subset["customer_satisfaction_rating"]
            .isna()
            .sum(),
        )

    print()
    print("=" * 70)
    print("Ticket lifecycle inspection complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()