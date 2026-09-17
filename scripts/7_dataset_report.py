import pandas as pd


DATASET_PATH = (
    "data/processed/support_tickets_clean.csv"
)


def print_distribution(
    df: pd.DataFrame,
    column: str,
) -> None:
    print()
    print(column)
    print("-" * len(column))

    counts = (
        df[column]
        .value_counts(
            dropna=False,
        )
    )

    percentages = (
        df[column]
        .value_counts(
            normalize=True,
            dropna=False,
        )
        .mul(100)
        .round(2)
    )

    report = pd.DataFrame(
        {
            "count": counts,
            "percent": percentages,
        }
    )

    print(report.to_string())


def main() -> None:
    df = pd.read_csv(DATASET_PATH)

    print("=" * 70)
    print("SupportCommander Dataset Report")
    print("=" * 70)

    print(f"Total tickets: {len(df):,}")
    print(f"Total columns: {len(df.columns)}")

    print_distribution(
        df,
        "ticket_type",
    )

    print_distribution(
        df,
        "ticket_status",
    )

    print_distribution(
        df,
        "ticket_priority",
    )

    print_distribution(
        df,
        "ticket_channel",
    )

    print_distribution(
        df,
        "lifecycle_state",
    )

    print()
    print("Top 15 purchased products")
    print("-------------------------")

    print(
        df["product_purchased"]
        .value_counts()
        .head(15)
        .to_string()
    )

    print()
    print("Customer satisfaction")
    print("---------------------")

    satisfaction = (
        df[
            "customer_satisfaction_rating"
        ]
        .dropna()
    )

    print(
        satisfaction
        .describe()
        .to_string()
    )

    print()
    print("Missing values")
    print("--------------")

    missing = (
        df.isna()
        .sum()
    )

    print(
        missing[
            missing > 0
        ]
        .sort_values(
            ascending=False,
        )
        .to_string()
    )

    print()
    print("=" * 70)
    print("Dataset report complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()