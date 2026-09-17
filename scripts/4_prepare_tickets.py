'''
Data preparation script for the customer support tickets dataset.
'''

from pathlib import Path
import pandas as pd

RAW_DATA_PATH = Path("data/raw/customer_support_tickets.csv")
PROCESSED_DATA_DIR = Path("data/processed")
OUTPUT_PATH = PROCESSED_DATA_DIR / "support_tickets_clean.csv"


COLUMN_MAPPING = {
    "Ticket ID": "ticket_id",
    "Customer Name": "customer_name",
    "Customer Email": "customer_email",
    "Customer Age": "customer_age",
    "Customer Gender": "customer_gender",
    "Product Purchased": "product_purchased",
    "Date of Purchase": "date_of_purchase",
    "Ticket Type": "ticket_type",
    "Ticket Subject": "ticket_subject",
    "Ticket Description": "ticket_description",
    "Ticket Status": "ticket_status",
    "Resolution": "resolution",
    "Ticket Priority": "ticket_priority",
    "Ticket Channel": "ticket_channel",
    "First Response Time": "first_response_time",
    "Time to Resolution": "time_to_resolution",
    "Customer Satisfaction Rating": "customer_satisfaction_rating",
}

lifecycle_mapping = {
    "Open": "awaiting_agent_response",
    "Pending Customer Response": "awaiting_customer",
    "Closed": "resolved",
}


EXPECTED_COLUMNS = set(COLUMN_MAPPING.keys())


def validate_raw_schema(df: pd.DataFrame) -> None:
    actual_columns = set(df.columns)
    missing_columns = EXPECTED_COLUMNS - actual_columns
    unexpected_columns = actual_columns - EXPECTED_COLUMNS

    if missing_columns:
        raise ValueError(f"Raw dataset is missing expected columns: {missing_columns}")
    if unexpected_columns:
        raise ValueError(f"Warning: Unexpected columns found in raw dataset: {unexpected_columns}")


def clean_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .replace(
            {
                "": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
                "null": pd.NA,
            }
        )
    )


def replace_product_placeholder(row: pd.Series) -> str | type(pd.NA):
    description = row["ticket_description"]
    product = row["product_purchased"]

    if pd.isna(description):
        return pd.NA

    if pd.isna(product):
        return description

    return description.replace("{product_purchased}", str(product),)


def get_lifecycle_state(status: str) -> str:
    mapping = {
        "Open": "awaiting_agent_response",
        "Pending Customer Response": "awaiting_customer",
        "Closed": "resolved",
    }

    return mapping.get(
        status,
        "unknown",
    )


def main() -> None:
    if not RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            f"Raw dataset not found: {RAW_DATA_PATH}"
        )

    print("=" * 70)
    print("SupportCommander Dataset Preparation")
    print("=" * 70)

    print(f"Reading dataset: {RAW_DATA_PATH}")

    df = pd.read_csv(RAW_DATA_PATH)

    print()
    print(f"Original rows: {len(df):,}")
    print(f"Original columns: {len(df.columns)}")

    validate_raw_schema(df)

    duplicate_rows = int(df.duplicated().sum())

    print(f"Duplicate rows detected: {duplicate_rows}")

    if duplicate_rows:
        df = df.drop_duplicates().copy()

    df = df.rename(columns=COLUMN_MAPPING)

    text_columns = [
        "customer_name",
        "customer_email",
        "customer_gender",
        "product_purchased",
        "ticket_type",
        "ticket_subject",
        "ticket_description",
        "ticket_status",
        "resolution",
        "ticket_priority",
        "ticket_channel",
    ]

    for column in text_columns:
        df[column] = clean_text(df[column])

    # Normalize email addresses.
    df["customer_email"] = (
        df["customer_email"]
        .str.lower()
        .str.strip()
    )

    # Replace literal placeholder text in ticket descriptions.
    placeholder_count = (
        df["ticket_description"]
        .str.contains(
            "{product_purchased}",
            regex=False,
            na=False,
        )
        .sum()
    )

    print(
        "Descriptions containing "
        f"{{product_purchased}} placeholder: "
        f"{placeholder_count:,}"
    )

    df["ticket_description"] = df.apply(
        replace_product_placeholder,
        axis=1,
    )


    df["ticket_text"] = (
        "Subject: "
        + df["ticket_subject"].fillna("")
        + "\n\nDescription: "
        + df["ticket_description"].fillna(""))

    # Required identifier.
    df["ticket_id"] = pd.to_numeric(
        df["ticket_id"],
        errors="coerce",
    ).astype("Int64")

    missing_ticket_ids = int(
        df["ticket_id"].isna().sum()
    )

    if missing_ticket_ids:
        raise ValueError(
            f"Found {missing_ticket_ids} missing ticket IDs."
        )

    duplicate_ticket_ids = int(
        df["ticket_id"].duplicated().sum()
    )

    if duplicate_ticket_ids:
        raise ValueError(
            f"Found {duplicate_ticket_ids} duplicate ticket IDs."
        )

    # Required ticket content.
    missing_descriptions = int(
        df["ticket_description"].isna().sum()
    )

    if missing_descriptions:
        raise ValueError(
            f"Found {missing_descriptions} missing ticket descriptions."
        )

    missing_subjects = int(
        df["ticket_subject"].isna().sum()
    )

    if missing_subjects:
        raise ValueError(
            f"Found {missing_subjects} missing ticket subjects."
        )

    df["lifecycle_state"] = (df["ticket_status"].map(get_lifecycle_state))

    # Numeric fields.
    df["customer_age"] = pd.to_numeric(
        df["customer_age"],
        errors="coerce",
    ).astype("Int64")

    df["customer_satisfaction_rating"] = pd.to_numeric(
        df["customer_satisfaction_rating"],
        errors="coerce",
    )

    # Date / timestamp fields.
    df["date_of_purchase"] = pd.to_datetime(
        df["date_of_purchase"],
        errors="coerce",
    )

    df["first_response_time"] = pd.to_datetime(
        df["first_response_time"],
        errors="coerce",
    )

    df["time_to_resolution"] = pd.to_datetime(
        df["time_to_resolution"],
        errors="coerce",
    )

    # Add explicit lifecycle flags.
    df["is_closed"] = (
        df["ticket_status"]
        .str.casefold()
        .eq("closed")
    )

    df["has_resolution"] = (
        df["resolution"].notna()
    )

    df["has_first_response"] = (
        df["first_response_time"].notna()
    )

    df["has_resolution_timestamp"] = (
        df["time_to_resolution"].notna()
    )

    df["has_satisfaction_rating"] = (
        df["customer_satisfaction_rating"].notna()
    )

    # Add provenance.
    df["dataset_source"] = (
        "kaggle_suraj520_customer_support_ticket_dataset"
    )

    df["dataset_record_type"] = "source_ticket"

    # Stable ordering.
    df = (
        df.sort_values("ticket_id")
        .reset_index(drop=True)
    )

    PROCESSED_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print(f"Final rows: {len(df):,}")
    print(f"Final columns: {len(df.columns)}")

    print()
    print("Missing values after cleaning:")

    missing_values = (
        df.isna()
        .sum()
        .sort_values(ascending=False)
    )

    print(
        missing_values[
            missing_values > 0
        ].to_string()
    )

    print()
    print("Ticket status distribution:")
    print(
        df["ticket_status"]
        .value_counts()
        .to_string()
    )

    print()
    print("Ticket type distribution:")
    print(
        df["ticket_type"]
        .value_counts()
        .to_string()
    )

    print()
    print(f"Output written to: {OUTPUT_PATH}")

    print()
    print("=" * 70)
    print("Dataset preparation successful!")
    print("=" * 70)


if __name__ == "__main__":
    main()