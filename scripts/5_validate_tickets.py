from pathlib import Path

import pandas as pd


DATASET_PATH = Path("data/processed/support_tickets_clean.csv")

REQUIRED_COLUMNS = {
    "ticket_id",
    "customer_name",
    "customer_email",
    "product_purchased",
    "ticket_type",
    "ticket_subject",
    "ticket_description",
    "ticket_status",
    "ticket_priority",
    "ticket_channel",
    "is_closed",
    "dataset_source",
    "dataset_record_type",
}

EXPECTED_TICKET_TYPES = {
    "Refund request",
    "Technical issue",
    "Cancellation request",
    "Product inquiry",
    "Billing inquiry",
}

EXPECTED_STATUSES = {
    "Open",
    "Closed",
    "Pending Customer Response",
}

EXPECTED_PRIORITIES = {
    "Low",
    "Medium",
    "High",
    "Critical",
}

EXPECTED_CHANNELS = {
    "Email",
    "Phone",
    "Chat",
    "Social media",
}


def validate_category(df: pd.DataFrame, column: str, expected_values: set[str]) -> None:
    actual_values = set(df[column].dropna().unique().tolist())
    unexpected = actual_values - expected_values

    if unexpected:
        raise ValueError(
            f"Unexpected values in {column}: "
            f"{sorted(unexpected)}"
        )


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Processed dataset not found: "
            f"{DATASET_PATH}"
        )

    df = pd.read_csv(DATASET_PATH)

    print("=" * 70)
    print("SupportCommander Dataset Validation")
    print("=" * 70)

    print(f"Rows: {len(df):,}")
    print(f"Columns: {len(df.columns)}")

    missing_required_columns = (
        REQUIRED_COLUMNS - set(df.columns)
    )

    if missing_required_columns:
        raise ValueError(
            "Missing required columns: "
            f"{sorted(missing_required_columns)}"
        )

    print("Required columns: OK")

    if df.empty:
        raise ValueError(
            "Processed dataset is empty."
        )

    if df["ticket_id"].isna().any():
        raise ValueError(
            "ticket_id contains missing values."
        )

    if df["ticket_id"].duplicated().any():
        raise ValueError(
            "ticket_id contains duplicate values."
        )

    print("Ticket IDs: OK")

    if df["ticket_description"].isna().any():
        raise ValueError(
            "ticket_description contains missing values."
        )

    empty_descriptions = int(
        df["ticket_description"]
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    if empty_descriptions:
        raise ValueError(
            f"Found {empty_descriptions} empty descriptions."
        )

    placeholder_count = int(
        df["ticket_description"]
        .astype(str)
        .str.contains(
            "{product_purchased}",
            regex=False,
        )
        .sum()
    )

    if placeholder_count:
        raise ValueError(
            f"Found {placeholder_count} unresolved "
            "{product_purchased} placeholders."
        )

    print("Ticket descriptions: OK")

    if df["ticket_subject"].isna().any():
        raise ValueError(
            "ticket_subject contains missing values."
        )

    print("Ticket subjects: OK")

    validate_category(
        df,
        "ticket_type",
        EXPECTED_TICKET_TYPES,
    )

    validate_category(
        df,
        "ticket_status",
        EXPECTED_STATUSES,
    )

    validate_category(
        df,
        "ticket_priority",
        EXPECTED_PRIORITIES,
    )

    validate_category(
        df,
        "ticket_channel",
        EXPECTED_CHANNELS,
    )

    print("Categorical values: OK")

    closed_tickets = (
        df["ticket_status"] == "Closed"
    )

    closed_without_resolution = int(
        (
            closed_tickets
            & df["resolution"].isna()
        ).sum()
    )

    print()
    print(
        "Closed tickets without resolution:",
        closed_without_resolution,
    )

    invalid_ratings = int(
        (
            df["customer_satisfaction_rating"]
            .dropna()
            .lt(1)
            |
            df["customer_satisfaction_rating"]
            .dropna()
            .gt(5)
        ).sum()
    )

    if invalid_ratings:
        raise ValueError(
            f"Found {invalid_ratings} satisfaction "
            "ratings outside 1-5."
        )

    print("Satisfaction rating range: OK")

    invalid_ages = int(
        (
            (df["customer_age"] < 18)
            |
            (df["customer_age"] > 120)
        ).sum()
    )

    if invalid_ages:
        print(
            "Warning: unusual customer ages found:",
            invalid_ages,
        )
    else:
        print("Customer age range: OK")

    print()
    print("Ticket types:")
    print(
        df["ticket_type"]
        .value_counts()
        .to_string()
    )

    print()
    print("Statuses:")
    print(
        df["ticket_status"]
        .value_counts()
        .to_string()
    )

    print()
    print("Priorities:")
    print(
        df["ticket_priority"]
        .value_counts()
        .to_string()
    )

    print()
    print("Channels:")
    print(
        df["ticket_channel"]
        .value_counts()
        .to_string()
    )

    print()
    print("=" * 70)
    print("Dataset validation successful!")
    print("=" * 70)


if __name__ == "__main__":
    main()