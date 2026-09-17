from pathlib import Path

import pandas as pd


RAW_DATA_DIR = Path("data/raw")


def find_csv_files() -> list[Path]:
    return sorted(RAW_DATA_DIR.glob("*.csv"))


def main() -> None:
    csv_files = find_csv_files()

    if not csv_files:
        raise FileNotFoundError(
            "No CSV files found in data/raw. "
            "Download the Kaggle dataset first."
        )

    print("=" * 70)
    print("SupportCommander Dataset Inspection")
    print("=" * 70)

    print("\nCSV files found:")

    for csv_file in csv_files:
        print(f" - {csv_file}")

    dataset_path = csv_files[0]

    print(f"\nUsing dataset: {dataset_path}")

    df = pd.read_csv(dataset_path)

    print("\nShape:")
    print(df.shape)

    print("\nColumns:")

    for column in df.columns:
        print(f" - {column}")

    print("\nData types:")
    print(df.dtypes)

    print("\nMissing values:")
    print(df.isna().sum())

    print("\nDuplicate rows:")
    print(df.duplicated().sum())

    print("\nFirst 3 rows:")
    print(df.head(3).to_string())

    print("\nUnique values for useful categorical columns:")

    candidate_columns = [
        "Ticket Type",
        "Ticket Status",
        "Ticket Priority",
        "Ticket Channel",
    ]

    for column in candidate_columns:
        if column in df.columns:
            print(f"\n{column}:")
            print(df[column].value_counts(dropna=False).head(20))

    print("\n" + "=" * 70)
    print("Dataset inspection complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()