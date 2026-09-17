from __future__ import annotations

import hashlib
from hmac import digest
import json
import random
from pathlib import Path
from typing import Any, AnyStr

import pandas as pd

SOURCE_PATH = Path("data/processed/support_tickets_clean.csv")
OUTPUT_PATH = Path("data/processed/domain")
RANDOM_SEED = 42

PRODUCT_PRICE_RANGES = {
    "GoPro Hero": (250, 500),
    "LG Smart TV": (500, 1800),
    "Dell XPS": (800, 2200),
}


DEFAULT_PRICE_RANGE = (
    100,
    1500,
)


PAYMENT_METHODS = [
    "credit_card",
    "debit_card",
    "paypal",
    "bank_transfer",
]


CARRIERS = [
    "DHL",
    "FedEx",
    "UPS",
]

CUSTOMER_TIERS = [
    "standard",
    "plus",
    "premium",
]


def stable_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def deterministic_rng(value: str,) -> random.Random:
    return random.Random(RANDOM_SEED + stable_seed(value))


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def get_price(product: str, rng: random.Random) -> float:
    low, high = PRODUCT_PRICE_RANGES.get(product, DEFAULT_PRICE_RANGE)
    return round(rng.uniform(low, high), 2)


def generate_customer(customer_id: str, row: pd.Series) -> dict[str, Any]:
    rng = deterministic_rng(customer_id)
    tier = rng.choice(CUSTOMER_TIERS)
    risk_roll = rng.random()

    if risk_roll < 0.03:
        risk_level = "high"
    elif risk_roll < 0.15:
        risk_level = "medium"
    else:
        risk_level = "low"

    account_status = (
        "restricted"
        if risk_level == "high"
        and rng.random() < 0.25
        else "active"
    )

    return {
        "customer_id": customer_id,
        "name": row["customer_name"],
        "email": row["customer_email"],
        "age": (
            int(row["customer_age"])
            if pd.notna(row["customer_age"])
            else None
        ),
        "gender": row["customer_gender"],
        "customer_tier": tier,
        "account_status": account_status,
        "risk_level": risk_level,
        "synthetic": True,
        "record_source": (
            "supportcommander_generated"
        ),
    }


def generate_order(order_id: str, customer_id: str, row: pd.Series,) -> dict[str, Any]:
    rng = deterministic_rng(order_id)
    amount = get_price(row["product_purchased"], rng,)
    return {
        "order_id": order_id,
        "ticket_id": int(
            row["ticket_id"]
        ),
        "customer_id": customer_id,
        "product": row[
            "product_purchased"
        ],
        "purchase_date": (
            row["date_of_purchase"]
            if pd.notna(
                row["date_of_purchase"]
            )
            else None
        ),
        "order_amount": amount,
        "currency": "USD",
        "order_status": "delivered",
        "synthetic": True,
        "record_source": (
            "supportcommander_generated"
        ),
    }


def generate_payment(payment_id: str, order: dict[str, Any]) -> dict[str, Any]:
    rng = deterministic_rng(payment_id)

    return {
        "payment_id": payment_id,
        "order_id": order["order_id"],
        "customer_id": (
            order["customer_id"]
        ),
        "amount": (
            order["order_amount"]
        ),
        "currency": order["currency"],
        "payment_method": rng.choice(
            PAYMENT_METHODS
        ),
        "payment_status": "paid",
        "synthetic": True,
        "record_source": (
            "supportcommander_generated"
        ),
    }


def generate_shipment(shipment_id: str, order: dict[str, Any],) -> dict[str, Any]:
    rng = deterministic_rng(shipment_id)

    return {
        "shipment_id": shipment_id,
        "order_id": order["order_id"],
        "customer_id": (
            order["customer_id"]
        ),
        "carrier": rng.choice(
            CARRIERS
        ),
        "tracking_number": (
            f"SC{shipment_id.split('-')[-1]}"
        ),
        "shipment_status": "delivered",
        "synthetic": True,
        "record_source": (
            "supportcommander_generated"
        ),
    }


def generate_refund(refund_id: str, row: pd.Series, order: dict[str, Any]) -> dict[str, Any]:
    status = row["ticket_status"]

    if status == "Closed":
        refund_status = "completed"
    elif status == (
        "Pending Customer Response"
    ):
        refund_status = "pending"
    else:
        refund_status = "requested"

    return {
        "refund_id": refund_id,
        "ticket_id": int(
            row["ticket_id"]
        ),
        "order_id": order["order_id"],
        "customer_id": (
            order["customer_id"]
        ),
        "refund_amount": (
            order["order_amount"]
        ),
        "currency": order["currency"],
        "refund_status": refund_status,
        "reason": (
            row["ticket_subject"]
        ),
        "synthetic": True,
        "record_source": (
            "supportcommander_generated"
        ),
    }


def should_generate_replacement(row: pd.Series,) -> bool:
    if (row["ticket_type"] != "Technical issue"):
        return False

    rng = deterministic_rng(f"replacement-{row['ticket_id']}")

    # Only a subset of historical
    # technical cases received replacements.
    return rng.random() < 0.25


def generate_replacement(replacement_id: str, row: pd.Series, order: dict[str, Any],) -> dict[str, Any]:

    if row["ticket_status"] == "Closed":
        status = "completed"
    elif row["ticket_status"] == ("Pending Customer Response"):
        status = "approved"
    else:
        status = "requested"

    return {
        "replacement_id": (
            replacement_id
        ),
        "ticket_id": int(
            row["ticket_id"]
        ),
        "order_id": order["order_id"],
        "customer_id": (
            order["customer_id"]
        ),
        "product": order["product"],
        "replacement_status": status,
        "reason": row["ticket_subject"],
        "synthetic": True,
        "record_source": (
            "supportcommander_generated"
        ),
    }



def main() -> None:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(
            f"Clean dataset not found: "
            f"{SOURCE_PATH}"
        )

    print("=" * 70)
    print(
        "SupportCommander Domain Data Generation"
    )
    print("=" * 70)

    df = pd.read_csv(
        SOURCE_PATH
    )

    print(
        f"Source tickets: {len(df):,}"
    )

    OUTPUT_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    customers = []
    orders = []
    payments = []
    shipments = []
    refunds = []
    replacements = []
    tickets = []

    customer_id_by_email = {}

    customer_counter = 1

    refund_counter = 1
    replacement_counter = 1

    for _, row in df.iterrows():

        email = row[
            "customer_email"
        ]

        if (
            email
            not in customer_id_by_email
        ):
            customer_id = (
                f"CUST-"
                f"{customer_counter:06d}"
            )

            customer_id_by_email[
                email
            ] = customer_id

            customers.append(
                generate_customer(
                    customer_id,
                    row,
                )
            )

            customer_counter += 1

        customer_id = (
            customer_id_by_email[email]
        )

        ticket_id = int(
            row["ticket_id"]
        )

        order_id = (
            f"ORD-{ticket_id:06d}"
        )

        payment_id = (
            f"PAY-{ticket_id:06d}"
        )

        shipment_id = (
            f"SHP-{ticket_id:06d}"
        )

        order = generate_order(
            order_id,
            customer_id,
            row,
        )

        payment = generate_payment(
            payment_id,
            order,
        )

        shipment = generate_shipment(
            shipment_id,
            order,
        )

        orders.append(order)
        payments.append(payment)
        shipments.append(shipment)

        refund_id = None

        if (
            row["ticket_type"]
            == "Refund request"
        ):
            refund_id = (
                f"REF-"
                f"{refund_counter:06d}"
            )

            refunds.append(
                generate_refund(
                    refund_id,
                    row,
                    order,
                )
            )

            refund_counter += 1

        replacement_id = None

        if should_generate_replacement(
            row
        ):
            replacement_id = (
                f"REP-"
                f"{replacement_counter:06d}"
            )

            replacements.append(
                generate_replacement(
                    replacement_id,
                    row,
                    order,
                )
            )

            replacement_counter += 1

        ticket_record = (
            row.where(
                pd.notna(row),
                None,
            )
            .to_dict()
        )

        ticket_record[
            "ticket_id"
        ] = ticket_id

        ticket_record[
            "customer_id"
        ] = customer_id

        ticket_record[
            "order_id"
        ] = order_id

        ticket_record[
            "payment_id"
        ] = payment_id

        ticket_record[
            "shipment_id"
        ] = shipment_id

        ticket_record[
            "refund_id"
        ] = refund_id

        ticket_record[
            "replacement_id"
        ] = replacement_id

        tickets.append(
            ticket_record
        )

    files = {
        "customers.jsonl": customers,
        "orders.jsonl": orders,
        "payments.jsonl": payments,
        "shipments.jsonl": shipments,
        "refunds.jsonl": refunds,
        "replacements.jsonl": replacements,
        "tickets.jsonl": tickets,
    }

    for filename, records in files.items():
        path = (
            OUTPUT_PATH
            / filename
        )

        write_jsonl(
            path,
            records,
        )

        print(
            f"{filename:<25} "
            f"{len(records):>8,}"
        )

    print()
    print(
        "Domain generation successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
