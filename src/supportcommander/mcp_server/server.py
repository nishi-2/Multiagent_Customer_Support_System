from __future__ import annotations

from fastmcp import FastMCP

from supportcommander.mcp_server.models import (
    SupportToolResult,
    TransactionToolResult,
)
from supportcommander.mcp_server.support_tools import (
    cancel_order_record,
    create_replacement_record,
    find_customer,
    find_order,
    find_payment,
    find_refund_history,
    find_replacement_history,
    find_shipment,
    issue_refund_record,
)


mcp = FastMCP(name="SupportCommander MCP Server")


@mcp.tool
def health() -> dict[str, str]:
    """
    Check whether the SupportCommander MCP server is available.
    """

    return {"status": "ok", "server": "SupportCommander MCP Server"}


@mcp.tool
def get_customer(customer_id: str) -> SupportToolResult:
    """
    Retrieve a customer by customer ID. Read-only tool.
    """

    customer = find_customer(customer_id)

    if customer is None:
        return SupportToolResult(
            success=False,
            error=f"Customer {customer_id} was not found.",
        )

    return SupportToolResult(success=True, data=customer)


@mcp.tool
def get_order(order_id: str) -> SupportToolResult:
    """
    Retrieve an order by order ID. Read-only tool.
    """

    order = find_order(order_id)

    if order is None:
        return SupportToolResult(success=False, error=f"Order {order_id} was not found.")

    return SupportToolResult(success=True, data=order)


@mcp.tool
def get_payment(order_id: str) -> SupportToolResult:
    """
    Retrieve the payment associated with an order. Read-only tool.
    """

    payment = find_payment(order_id)

    if payment is None:
        return SupportToolResult(
            success=False,
            error=f"No payment found for order {order_id}.",
        )

    return SupportToolResult(success=True, data=payment)


@mcp.tool
def get_shipment(order_id: str) -> SupportToolResult:
    """
    Retrieve shipment information for an order. Read-only tool.
    """

    shipment = find_shipment(order_id)

    if shipment is None:
        return SupportToolResult(
            success=False,
            error=f"No shipment found for order {order_id}.",
        )

    return SupportToolResult(success=True, data=shipment)


@mcp.tool
def get_refund_history(customer_id: str) -> SupportToolResult:
    """
    Retrieve all refund records associated with a customer. Read-only tool.
    """

    refunds = find_refund_history(customer_id)

    return SupportToolResult(success=True, data=refunds)


@mcp.tool
def get_replacement_history(customer_id: str) -> SupportToolResult:
    """
    Retrieve all replacement records associated with a customer. Read-only tool.
    """

    replacements = find_replacement_history(customer_id)

    return SupportToolResult(success=True, data=replacements)


@mcp.tool
def issue_refund(
    order_id: str,
    customer_id: str,
    amount: float,
    reason: str,
) -> TransactionToolResult:
    """
    Execute an approved refund.

    This tool changes backend state.
    """

    try:
        record = issue_refund_record(
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            reason=reason,
        )

        return TransactionToolResult(
            success=True,
            transaction_id=(
                record["refund_id"]
            ),
            data=record,
        )

    except Exception as exc:
        return TransactionToolResult(
            success=False,
            error=str(exc),
        )


@mcp.tool
def create_replacement(
    order_id: str,
    customer_id: str,
    reason: str,
) -> TransactionToolResult:
    """
    Create a replacement order for a customer.

    This tool changes backend state.
    """

    try:
        record = (
            create_replacement_record(
                order_id=order_id,
                customer_id=customer_id,
                reason=reason,
            )
        )

        return TransactionToolResult(
            success=True,
            transaction_id=(
                record[
                    "replacement_id"
                ]
            ),
            data=record,
        )

    except Exception as exc:
        return TransactionToolResult(
            success=False,
            error=str(exc),
        )


@mcp.tool
def cancel_order(
    order_id: str,
    customer_id: str,
    reason: str,
) -> TransactionToolResult:
    """
    Cancel an order on behalf of a customer.

    This tool changes backend state.
    """

    try:
        record = cancel_order_record(
            order_id=order_id,
            customer_id=customer_id,
            reason=reason,
        )

        return TransactionToolResult(
            success=True,
            transaction_id=order_id,
            data=record,
        )

    except Exception as exc:
        return TransactionToolResult(
            success=False,
            error=str(exc),
        )


if __name__ == "__main__":
    mcp.run()