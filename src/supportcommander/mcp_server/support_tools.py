from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from typing import Any
from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from supportcommander.db.mongo import get_database


def find_customer(customer_id: str) -> dict[str, Any] | None:
    db = get_database()
    return db.customers.find_one({"customer_id": customer_id}, {"_id": 0})


def find_order(order_id: str) -> dict[str, Any] | None:
    db = get_database()
    return db.orders.find_one({"order_id": order_id}, {"_id": 0})


def find_payment(order_id: str) -> dict[str, Any] | None:
    db = get_database()
    return db.payments.find_one({"order_id": order_id}, {"_id": 0})


def find_shipment(order_id: str) -> dict[str, Any] | None:
    db = get_database()
    return db.shipments.find_one({"order_id": order_id}, {"_id": 0})


def find_refund_history(customer_id: str) -> list[dict[str, Any]]:
    db = get_database()
    return list(db.refunds.find({"customer_id": customer_id}, {"_id": 0}).sort("refund_id", 1))


def find_replacement_history(customer_id: str) -> list[dict[str, Any]]:
    db = get_database()
    return list(db.replacements.find({"customer_id": customer_id}, {"_id": 0}).sort("replacement_id", 1))


def issue_refund_record(
    *,
    order_id: str,
    customer_id: str,
    amount: float,
    reason: str,
) -> dict:

    db = get_database()

    order = db.orders.find_one(
        {
            "order_id": order_id,
            "customer_id": customer_id,
        }
    )

    if order is None:
        raise ValueError(
            "Order does not belong "
            "to the customer."
        )

    payment = db.payments.find_one(
        {
            "order_id": order_id,
        }
    )

    if payment is None:
        raise ValueError(
            "Payment record not found."
        )

    existing = db.refunds.find_one(
        {
            "order_id": order_id,
            "customer_id": customer_id,
            "status": "completed",
        }
    )

    if existing is not None:
        raise ValueError(
            "A completed refund already exists "
            "for this order."
        )

    refund_id = (
        f"RFD-{uuid4().hex[:12].upper()}"
    )

    record = {
        "refund_id": refund_id,
        "order_id": order_id,
        "customer_id": customer_id,
        "amount": float(amount),
        "reason": reason,
        "status": "completed",
        "created_at": datetime.now(
            timezone.utc
        ),
        "synthetic": True,
        "record_source":
            "supportcommander_transaction",
    }

    try:
        db.refunds.insert_one(record)
    except DuplicateKeyError:
        raise ValueError(
            "A completed refund already exists "
            "for this order (duplicate key)."
        )

    record.pop("_id", None)

    return record


def create_replacement_record(
    *,
    order_id: str,
    customer_id: str,
    reason: str,
) -> dict:

    db = get_database()

    order = db.orders.find_one(
        {
            "order_id": order_id,
            "customer_id": customer_id,
        }
    )

    if order is None:
        raise ValueError(
            "Order does not belong "
            "to the customer."
        )

    existing = (
        db.replacements.find_one(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "status": {
                    "$in": [
                        "created",
                        "shipped",
                        "delivered",
                        "completed",
                    ]
                },
            }
        )
    )

    if existing is not None:
        raise ValueError(
            "A replacement already exists "
            "for this order."
        )

    replacement_id = (
        f"RPL-{uuid4().hex[:12].upper()}"
    )

    record = {
        "replacement_id":
            replacement_id,

        "order_id":
            order_id,

        "customer_id":
            customer_id,

        "reason":
            reason,

        "status":
            "created",

        "created_at":
            datetime.now(
                timezone.utc
            ),

        "synthetic":
            True,

        "record_source":
            "supportcommander_transaction",
    }

    db.replacements.insert_one(
        record
    )

    record.pop("_id", None)

    return record


def cancel_order_record(
    *,
    order_id: str,
    customer_id: str,
    reason: str,
) -> dict:

    db = get_database()

    order = db.orders.find_one(
        {
            "order_id": order_id,
            "customer_id": customer_id,
        }
    )

    if order is None:
        raise ValueError(
            "Order does not belong "
            "to the customer."
        )

    if str(
        order.get(
            "order_status",
            ""
        )
    ).lower() == "cancelled":
        raise ValueError(
            "Order is already cancelled."
        )

    result = db.orders.update_one(
        {
            "order_id": order_id,
        },
        {
            "$set": {
                "order_status":
                    "cancelled",

                "cancellation_reason":
                    reason,

                "cancelled_at":
                    datetime.now(
                        timezone.utc
                    ),
            }
        },
    )

    if result.modified_count != 1:
        raise ValueError(
            "Order cancellation "
            "did not modify a record."
        )

    return {
        "order_id": order_id,
        "status": "cancelled",
    }