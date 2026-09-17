from supportcommander.mcp_server.support_tools import (
    find_customer,
    find_order,
    find_payment,
    find_refund_history,
    find_replacement_history,
    find_shipment,
)


def main() -> None:
    print("=" * 70)
    print("SupportCommander Support Tool Check")
    print("=" * 70)

    customer = find_customer(
        "CUST-000001"
    )

    if customer is None:
        raise RuntimeError(
            "Customer lookup failed."
        )

    print("Customer lookup: OK")

    order = find_order(
        "ORD-000001"
    )

    if order is None:
        raise RuntimeError(
            "Order lookup failed."
        )

    print("Order lookup: OK")

    payment = find_payment(
        "ORD-000001"
    )

    if payment is None:
        raise RuntimeError(
            "Payment lookup failed."
        )

    print("Payment lookup: OK")

    shipment = find_shipment(
        "ORD-000001"
    )

    if shipment is None:
        raise RuntimeError(
            "Shipment lookup failed."
        )

    print("Shipment lookup: OK")

    refunds = find_refund_history(
        "CUST-000001"
    )

    print(
        "Refund history lookup: OK",
        f"({len(refunds)} records)",
    )

    replacements = (
        find_replacement_history(
            "CUST-000001"
        )
    )

    print(
        "Replacement history lookup: OK",
        f"({len(replacements)} records)",
    )

    print()
    print("=" * 70)
    print(
        "Support tool data check successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
