from supportcommander.db.mongo import (
    get_database,
    ping_database,
)


EXPECTED_TICKETS = 8469


def main() -> None:

    print("=" * 70)
    print(
        "SupportCommander MongoDB "
        "Domain Validation"
    )
    print("=" * 70)

    ping_database()

    print("MongoDB connection: OK")

    db = get_database()

    collections = [
        "customers",
        "orders",
        "payments",
        "shipments",
        "refunds",
        "replacements",
        "tickets",
    ]

    print()

    counts = {}

    for collection_name in collections:

        count = db[
            collection_name
        ].count_documents({})

        counts[
            collection_name
        ] = count

        print(
            f"{collection_name:<15} "
            f"{count:>8,}"
        )

    if (
        counts["tickets"]
        != EXPECTED_TICKETS
    ):
        raise ValueError(
            "Unexpected ticket count: "
            f"{counts['tickets']}"
        )

    if (
        counts["orders"]
        != EXPECTED_TICKETS
    ):
        raise ValueError(
            "Every ticket should currently "
            "have one linked order."
        )

    if (
        counts["payments"]
        != EXPECTED_TICKETS
    ):
        raise ValueError(
            "Every order should currently "
            "have one linked payment."
        )

    if (
        counts["shipments"]
        != EXPECTED_TICKETS
    ):
        raise ValueError(
            "Every order should currently "
            "have one linked shipment."
        )

    if (
        counts["refunds"]
        != 1752
    ):
        raise ValueError(
            "Refund count should match "
            "refund request tickets."
        )

    sample_ticket = (
        db.tickets.find_one(
            {
                "ticket_id": 1
            }
        )
    )

    if sample_ticket is None:
        raise ValueError(
            "Could not find sample ticket."
        )

    customer = (
        db.customers.find_one(
            {
                "customer_id":
                sample_ticket[
                    "customer_id"
                ]
            }
        )
    )

    if customer is None:
        raise ValueError(
            "Sample ticket customer "
            "reference is broken."
        )

    order = (
        db.orders.find_one(
            {
                "order_id":
                sample_ticket[
                    "order_id"
                ]
            }
        )
    )

    if order is None:
        raise ValueError(
            "Sample ticket order "
            "reference is broken."
        )

    payment = (
        db.payments.find_one(
            {
                "order_id":
                order[
                    "order_id"
                ]
            }
        )
    )

    if payment is None:
        raise ValueError(
            "Sample order payment "
            "reference is broken."
        )

    shipment = (
        db.shipments.find_one(
            {
                "order_id":
                order[
                    "order_id"
                ]
            }
        )
    )

    if shipment is None:
        raise ValueError(
            "Sample order shipment "
            "reference is broken."
        )

    print()
    print(
        "Ticket → Customer: OK"
    )

    print(
        "Ticket → Order: OK"
    )

    print(
        "Order → Payment: OK"
    )

    print(
        "Order → Shipment: OK"
    )

    print()
    print("=" * 70)
    print(
        "MongoDB domain validation "
        "successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()