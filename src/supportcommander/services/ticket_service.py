from typing import Any

from supportcommander.db.mongo import get_database


def get_ticket(ticket_id: int) -> dict[str, Any] | None:
    db = get_database()
    return db.tickets.find_one(
        {"ticket_id": ticket_id},
        {"_id": 0},
    )


def list_tickets(*, limit: int = 20, skip: int = 0, ticket_status: str | None = None, ticket_type: str | None = None, ticket_priority: str | None = None,) -> list[dict[str, Any]]:

    db = get_database()
    query: dict[str, Any] = {}
    if ticket_status:
        query["ticket_status"] = ticket_status

    if ticket_type:
        query["ticket_type"] = ticket_type

    if ticket_priority:
        query["ticket_priority"] = ticket_priority

    cursor = db.tickets.find(query, {"_id": 0}).sort("ticket_id", 1).skip(skip).limit(limit)
    return list(cursor)



def count_tickets(*, ticket_status: str | None = None, ticket_type: str | None = None, ticket_priority: str | None = None,) -> int:
    db = get_database()
    query: dict[str, Any] = {}

    if ticket_status:
        query["ticket_status"] = ticket_status

    if ticket_type:
        query["ticket_type"] = ticket_type

    if ticket_priority:
        query["ticket_priority"] = ticket_priority

    return db.tickets.count_documents(query)


def get_ticket_context(ticket_id: int,) -> dict[str, Any] | None:

    db = get_database()
    ticket = get_ticket(ticket_id)

    if ticket is None:
        return None

    customer = db.customers.find_one(
        {
            "customer_id": ticket["customer_id"]
        },
        {
            "_id": 0,
        },
    )

    order = db.orders.find_one(
        {
            "order_id": ticket["order_id"]
        },
        {
            "_id": 0,
        },
    )

    payment = db.payments.find_one(
        {
            "order_id": ticket["order_id"]
        },
        {
            "_id": 0,
        },
    )

    shipment = db.shipments.find_one(
        {
            "shipment_id": ticket["shipment_id"]
        },
        {
            "_id": 0,
        },
    )

    refund = None

    if ticket.get("refund_id"):
        refund = db.refunds.find_one(
            {
                "refund_id": ticket["refund_id"]
            },
            {
                "_id": 0,
            },
        )

    replacement = None

    if ticket.get("replacement_id"):
        replacement = (
            db.replacements.find_one(
                {
                    "replacement_id":ticket["replacement_id"]
                },
                {
                    "_id": 0,
                },
            )
        )

    return {
        "ticket": ticket,
        "customer": customer,
        "order": order,
        "payment": payment,
        "shipment": shipment,
        "refund": refund,
        "replacement": replacement,
    }