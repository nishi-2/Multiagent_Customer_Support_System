import asyncio

from supportcommander.mcp_client.support_client import (
    get_customer,
    get_order,
    get_payment,
    get_refund_history,
    get_replacement_history,
    get_shipment,
)


async def main() -> None:

    print("=" * 70)
    print(
        "SupportCommander FastMCP "
        "STDIO Client Check"
    )
    print("=" * 70)

    customer = await get_customer(
        "CUST-000001"
    )

    assert customer[
        "success"
    ] is True

    print(
        "get_customer: OK"
    )

    order = await get_order(
        "ORD-000001"
    )

    assert order[
        "success"
    ] is True

    print(
        "get_order: OK"
    )

    payment = await get_payment(
        "ORD-000001"
    )

    assert payment[
        "success"
    ] is True

    print(
        "get_payment: OK"
    )

    shipment = await get_shipment(
        "ORD-000001"
    )

    assert shipment[
        "success"
    ] is True

    print(
        "get_shipment: OK"
    )

    refunds = (
        await get_refund_history(
            "CUST-000001"
        )
    )

    assert refunds[
        "success"
    ] is True

    print(
        "get_refund_history: OK"
    )

    replacements = (
        await get_replacement_history(
            "CUST-000001"
        )
    )

    assert replacements[
        "success"
    ] is True

    print(
        "get_replacement_history: OK"
    )

    print()
    print("=" * 70)
    print(
        "FastMCP STDIO client successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
