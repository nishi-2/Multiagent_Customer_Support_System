from __future__ import annotations

from typing import Any

from supportcommander.mcp_client.client import (
    get_shared_client,
)


class SupportMCPError(Exception):
    """SupportCommander MCP invocation failed."""


async def call_support_tool(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:

    client = get_shared_client()

    result = await client.call_tool(
        tool_name,
        arguments,
    )

    if result.structured_content is None:
        raise SupportMCPError(
            f"MCP tool {tool_name} "
            "returned no structured data."
        )

    return result.structured_content


async def get_customer(
    customer_id: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "get_customer",
        {
            "customer_id":
                customer_id,
        },
    )


async def get_order(
    order_id: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "get_order",
        {
            "order_id":
                order_id,
        },
    )


async def get_payment(
    order_id: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "get_payment",
        {
            "order_id":
                order_id,
        },
    )


async def get_shipment(
    order_id: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "get_shipment",
        {
            "order_id":
                order_id,
        },
    )


async def get_refund_history(
    customer_id: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "get_refund_history",
        {
            "customer_id":
                customer_id,
        },
    )


async def get_replacement_history(
    customer_id: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "get_replacement_history",
        {
            "customer_id":
                customer_id,
        },
    )


async def issue_refund(
    *,
    order_id: str,
    customer_id: str,
    amount: float,
    reason: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "issue_refund",
        {
            "order_id":
                order_id,

            "customer_id":
                customer_id,

            "amount":
                amount,

            "reason":
                reason,
        },
    )


async def create_replacement(
    *,
    order_id: str,
    customer_id: str,
    reason: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "create_replacement",
        {
            "order_id":
                order_id,

            "customer_id":
                customer_id,

            "reason":
                reason,
        },
    )


async def cancel_order(
    *,
    order_id: str,
    customer_id: str,
    reason: str,
) -> dict[str, Any]:

    return await call_support_tool(
        "cancel_order",
        {
            "order_id":
                order_id,

            "customer_id":
                customer_id,

            "reason":
                reason,
        },
    )
