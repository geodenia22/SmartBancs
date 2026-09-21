from pathlib import Path
import logging

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data" / "raw_transactions.csv"
OUTPUT_FILE = BASE_DIR / "output" / "clean_transactions.csv"

SUPPORTED_CURRENCIES = {"USD", "EUR"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("smartbancs.etl")


def extract() -> pd.DataFrame:
    logger.info("Extracting transactions from %s", INPUT_FILE)

    dataframe = pd.read_csv(INPUT_FILE)

    logger.info("Extracted %s raw transactions", len(dataframe))

    return dataframe


def transform(dataframe: pd.DataFrame) -> pd.DataFrame:
    df = dataframe.copy()

    # Standardize textual fields.
    df["currency"] = df["currency"].astype("string").str.strip().str.upper()
    df["status"] = df["status"].astype("string").str.strip().str.upper()

    # Convert amount to a numeric value.
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Normalize timestamps.
    df["created_at"] = pd.to_datetime(
        df["created_at"],
        errors="coerce",
        format="mixed",
        dayfirst=False,
    )

    # Remove records without the minimum information required for analysis.
    df = df.dropna(
        subset=[
            "transaction_id",
            "source_account_id",
            "destination_account_id",
            "amount",
            "created_at",
        ]
    )

    # Invalid financial transactions must not reach the analytical dataset.
    df = df[df["amount"] > 0]

    # Keep currencies supported by this MVP.
    df = df[df["currency"].isin(SUPPORTED_CURRENCIES)]

    # Fill a missing status with a controlled value.
    df["status"] = df["status"].fillna("UNKNOWN")

    # Features useful for analytics / AI.
    df["hour_of_day"] = df["created_at"].dt.hour
    df["is_night_transaction"] = (
        (df["hour_of_day"] < 6) | (df["hour_of_day"] >= 22)
    )

    # Standardized ISO representation.
    df["created_at"] = df["created_at"].dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Stable output order.
    df = df[
        [
            "transaction_id",
            "source_account_id",
            "destination_account_id",
            "amount",
            "currency",
            "status",
            "created_at",
            "hour_of_day",
            "is_night_transaction",
        ]
    ]

    return df.reset_index(drop=True)


def load(dataframe: pd.DataFrame) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    dataframe.to_csv(OUTPUT_FILE, index=False)

    logger.info(
        "Loaded %s clean transactions into %s",
        len(dataframe),
        OUTPUT_FILE,
    )


def main() -> None:
    logger.info("Starting SmartBancs ETL")

    raw_df = extract()
    clean_df = transform(raw_df)

    rejected_records = len(raw_df) - len(clean_df)

    load(clean_df)

    logger.info(
        "ETL completed: input=%s output=%s rejected=%s",
        len(raw_df),
        len(clean_df),
        rejected_records,
    )


if __name__ == "__main__":
    main()