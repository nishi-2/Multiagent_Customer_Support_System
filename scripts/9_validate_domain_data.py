import json
from pathlib import Path


DOMAIN_DIR = Path(
    "data/processed/domain"
)


def read_jsonl(
    filename: str,
) -> list[dict]:
    path = DOMAIN_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Missing domain file: {path}"
        )

    records = []

    with path.open(
        encoding="utf-8",
    ) as file:
        for line in file:
            records.append(
                json.loads(line)
            )

    return records


def ensure_unique(
    records: list[dict],
    field: str,
) -> None:
    values = [
        record[field]
        for record in records
    ]

    if len(values) != len(set(values)):
        raise ValueError(
            f"Duplicate {field} values found."
        )


def main() -> None:
    print("=" * 70)
    print(
        "SupportCommander Domain Validation"
    )
    print("=" * 70)

    customers = read_jsonl(
        "customers.jsonl"
    )

    orders = read_jsonl(
        "orders.jsonl"
    )

    payments = read_jsonl(
        "payments.jsonl"
    )

    shipments = read_jsonl(
        "shipments.jsonl"
    )

    refunds = read_jsonl(
        "refunds.jsonl"
    )

    replacements = read_jsonl(
        "replacements.jsonl"
    )

    tickets = read_jsonl(
        "tickets.jsonl"
    )

    ensure_unique(
        customers,
        "customer_id",
    )

    ensure_unique(
        orders,
        "order_id",
    )

    ensure_unique(
        payments,
        "payment_id",
    )

    ensure_unique(
        shipments,
        "shipment_id",
    )

    ensure_unique(
        refunds,
        "refund_id",
    )

    ensure_unique(
        replacements,
        "replacement_id",
    )

    ensure_unique(
        tickets,
        "ticket_id",
    )

    customer_ids = {
        item["customer_id"]
        for item in customers
    }

    order_ids = {
        item["order_id"]
        for item in orders
    }

    payment_ids = {
        item["payment_id"]
        for item in payments
    }

    shipment_ids = {
        item["shipment_id"]
        for item in shipments
    }

    refund_ids = {
        item["refund_id"]
        for item in refunds
    }

    replacement_ids = {
        item["replacement_id"]
        for item in replacements
    }

    for ticket in tickets:

        if (
            ticket["customer_id"]
            not in customer_ids
        ):
            raise ValueError(
                "Ticket references "
                "unknown customer."
            )

        if (
            ticket["order_id"]
            not in order_ids
        ):
            raise ValueError(
                "Ticket references "
                "unknown order."
            )

        if (
            ticket["payment_id"]
            not in payment_ids
        ):
            raise ValueError(
                "Ticket references "
                "unknown payment."
            )

        if (
            ticket["shipment_id"]
            not in shipment_ids
        ):
            raise ValueError(
                "Ticket references "
                "unknown shipment."
            )

        refund_id = (
            ticket.get(
                "refund_id"
            )
        )

        if (
            refund_id is not None
            and refund_id
            not in refund_ids
        ):
            raise ValueError(
                "Ticket references "
                "unknown refund."
            )

        replacement_id = (
            ticket.get(
                "replacement_id"
            )
        )

        if (
            replacement_id is not None
            and replacement_id
            not in replacement_ids
        ):
            raise ValueError(
                "Ticket references "
                "unknown replacement."
            )

    for order in orders:

        if (
            order["customer_id"]
            not in customer_ids
        ):
            raise ValueError(
                "Order references "
                "unknown customer."
            )

    for payment in payments:

        if (
            payment["order_id"]
            not in order_ids
        ):
            raise ValueError(
                "Payment references "
                "unknown order."
            )

    for shipment in shipments:

        if (
            shipment["order_id"]
            not in order_ids
        ):
            raise ValueError(
                "Shipment references "
                "unknown order."
            )

    for refund in refunds:

        if (
            refund["order_id"]
            not in order_ids
        ):
            raise ValueError(
                "Refund references "
                "unknown order."
            )

    for replacement in replacements:

        if (
            replacement["order_id"]
            not in order_ids
        ):
            raise ValueError(
                "Replacement references "
                "unknown order."
            )

    print(
        f"Customers:    {len(customers):,}"
    )

    print(
        f"Orders:       {len(orders):,}"
    )

    print(
        f"Payments:     {len(payments):,}"
    )

    print(
        f"Shipments:    {len(shipments):,}"
    )

    print(
        f"Refunds:      {len(refunds):,}"
    )

    print(
        f"Replacements: {len(replacements):,}"
    )

    print(
        f"Tickets:      {len(tickets):,}"
    )

    print()
    print("Unique IDs: OK")
    print("Customer references: OK")
    print("Order references: OK")
    print("Payment references: OK")
    print("Shipment references: OK")
    print("Refund references: OK")
    print("Replacement references: OK")

    print()
    print("=" * 70)
    print(
        "Domain validation successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()