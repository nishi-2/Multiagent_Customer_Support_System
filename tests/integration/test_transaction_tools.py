import pytest

from supportcommander.db.mongo import (
    get_database,
)
from supportcommander.mcp_client.support_client import (
    issue_refund,
)


@pytest.mark.asyncio
async def test_issue_refund():

    db = get_database()

    db.refunds.delete_many(
        {
            "order_id": "ORD-000001",
            "customer_id": "CUST-000001",
            "record_source": "supportcommander_transaction",
        }
    )

    result = await issue_refund(
        order_id="ORD-000001",
        customer_id="CUST-000001",
        amount=1.0,
        reason="integration test",
    )

    assert result[
        "success"
    ] is True

    assert result.get(
        "data"
    )

    refund_id = result[
        "data"
    ][
        "refund_id"
    ]

    db.refunds.delete_one(
        {
            "refund_id":
                refund_id
        }
    )
