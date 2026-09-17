import json
from pathlib import Path
from pymongo import ASCENDING

from supportcommander.db.mongo import get_database, ping_database

DOMAIN_DIR = Path("data/processed/domain")


COLLECTION_FILES = {
    "customers": "customers.jsonl",
    "orders": "orders.jsonl",
    "payments": "payments.jsonl",
    "shipments": "shipments.jsonl",
    "refunds": "refunds.jsonl",
    "replacements": "replacements.jsonl",
    "tickets": "tickets.jsonl",
}

def load_jsonl(path: Path,) -> list[dict]:
    records = []
    with path.open(encoding="utf-8",) as file:
        for line in file:
            records.append(json.loads(line))

    return records


def create_indexes(db,) -> None:

    db.customers.create_index([("customer_id", ASCENDING)], unique=True,)
    db.customers.create_index([("email", ASCENDING)])
    db.orders.create_index([("order_id", ASCENDING)], unique=True)
    db.orders.create_index([("customer_id", ASCENDING)])
    db.orders.create_index([("ticket_id", ASCENDING)])
    db.payments.create_index([("payment_id", ASCENDING)], unique=True)
    db.payments.create_index([("order_id", ASCENDING)])
    db.shipments.create_index([("shipment_id", ASCENDING)], unique=True)
    db.shipments.create_index([("order_id", ASCENDING)])
    db.refunds.create_index([("refund_id", ASCENDING)], unique=True)
    db.refunds.create_index([("customer_id", ASCENDING)])
    db.refunds.create_index([("order_id", ASCENDING)])
    db.replacements.create_index([("replacement_id", ASCENDING)], unique=True)
    db.replacements.create_index([("order_id", ASCENDING)])
    db.tickets.create_index([("ticket_id", ASCENDING)], unique=True)
    db.tickets.create_index([("customer_id", ASCENDING)])
    db.tickets.create_index([("order_id", ASCENDING)])
    db.tickets.create_index([("ticket_status", ASCENDING)])
    db.tickets.create_index([("ticket_type", ASCENDING)])
    db.tickets.create_index([("ticket_priority", ASCENDING)])
    db.workflows.create_index([("workflow_id", ASCENDING)], unique=True,)
    db.workflows.create_index([("ticket_id", ASCENDING)])


def main() -> None:
    print("=" * 70)
    print("SupportCommander MongoDB. Domain Loader")
    print("=" * 70)

    ping_database()

    print("MongoDB connection: OK")

    db = get_database()

    for collection_name, filename in COLLECTION_FILES.items():
        path = DOMAIN_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing file: {path}")

        records = load_jsonl(path)
        collection = db[collection_name]

        # Development loader: replace the generated dataset on every run.
        collection.delete_many({})

        if records:
            collection.insert_many(records, ordered=False)
        print(f"{collection_name:<15} {len(records):>8,}")

    create_indexes(db)

    print()
    print("MongoDB indexes created.")

    print()
    print("=" * 70)
    print("Domain data load successful!")
    print("=" * 70)


if __name__ == "__main__":
    main()
