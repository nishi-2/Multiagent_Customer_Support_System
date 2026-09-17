import asyncio

from fastmcp import Client

from supportcommander.mcp_server.server import mcp


async def main() -> None:

    print("=" * 70)
    print(
        "SupportCommander FastMCP Tool Check"
    )
    print("=" * 70)

    async with Client(mcp) as client:

        customer_result = (
            await client.call_tool(
                "get_customer",
                {
                    "customer_id":
                        "CUST-000001"
                },
            )
        )

        customer = (
            customer_result.structured_content
        )

        assert (
            customer["success"]
            is True
        )

        assert (
            customer["data"][
                "customer_id"
            ]
            == "CUST-000001"
        )

        print(
            "get_customer: OK"
        )

        order_result = (
            await client.call_tool(
                "get_order",
                {
                    "order_id":
                        "ORD-000001"
                },
            )
        )

        order = order_result.structured_content

        assert (
            order["success"]
            is True
        )

        assert (
            order["data"][
                "order_id"
            ]
            == "ORD-000001"
        )

        print(
            "get_order: OK"
        )

        payment_result = (
            await client.call_tool(
                "get_payment",
                {
                    "order_id":
                        "ORD-000001"
                },
            )
        )

        assert (
            payment_result.structured_content[
                "success"
            ]
            is True
        )

        print(
            "get_payment: OK"
        )

        shipment_result = (
            await client.call_tool(
                "get_shipment",
                {
                    "order_id":
                        "ORD-000001"
                },
            )
        )

        assert (
            shipment_result.structured_content[
                "success"
            ]
            is True
        )

        print(
            "get_shipment: OK"
        )

        missing = await client.call_tool(
            "get_customer",
            {
                "customer_id":
                    "CUST-999999"
            },
        )

        print(
            missing.structured_content
        )

        assert (
            missing.structured_content["success"]
            is False
        )

        assert (
            missing.structured_content["data"]
            is None
        )

        print(
            "missing customer (controlled failure): OK"
        )

    print()
    print("=" * 70)
    print(
        "FastMCP tool check successful!"
    )
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
