import pytest

from fastmcp import Client

from supportcommander.mcp_server.server import (
    mcp,
)


@pytest.mark.asyncio
async def test_customer_tool():

    async with Client(mcp) as client:

        result = await client.call_tool(
            "get_customer",
            {
                "customer_id":
                    "CUST-000001"
            },
        )

        assert (
            result.structured_content[
                "success"
            ]
            is True
        )

        assert (
            result.structured_content[
                "data"
            ][
                "customer_id"
            ]
            == "CUST-000001"
        )


@pytest.mark.asyncio
async def test_order_tool():

    async with Client(mcp) as client:

        result = await client.call_tool(
            "get_order",
            {
                "order_id":
                    "ORD-000001"
            },
        )

        assert (
            result.structured_content[
                "success"
            ]
            is True
        )

        assert (
            result.structured_content[
                "data"
            ][
                "order_id"
            ]
            == "ORD-000001"
        )


@pytest.mark.asyncio
async def test_missing_customer():

    async with Client(mcp) as client:

        result = await client.call_tool(
            "get_customer",
            {
                "customer_id":
                    "CUST-999999"
            },
        )

        assert (
            result.structured_content[
                "success"
            ]
            is False
        )

        assert (
            result.structured_content[
                "data"
            ]
            is None
        )
