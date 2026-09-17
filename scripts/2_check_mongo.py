from datetime import datetime, timezone

from supportcommander.core.config import get_settings
from supportcommander.db.mongo import get_database, ping_database


def main() -> None:
    settings = get_settings()

    print("=" * 50)
    print("SupportCommander MongoDB Check")
    print("=" * 50)

    print(f"Mongo host: {settings.mongo_host}")
    print(f"Mongo port: {settings.mongo_port}")
    print(f"Database:   {settings.mongo_db}")

    ping_database()

    print("MongoDB ping: OK")

    database = get_database()

    collection = database["system_checks"]

    document = {
        "service": "supportcommander",
        "check": "mongodb",
        "status": "ok",
        "checked_at": datetime.now(timezone.utc),
    }

    result = collection.insert_one(document)

    print(f"MongoDB write: OK")
    print(f"Inserted ID: {result.inserted_id}")

    saved_document = collection.find_one(
        {"_id": result.inserted_id}
    )

    if saved_document is None:
        raise RuntimeError("MongoDB document could not be read back.")

    print("MongoDB read: OK")

    print("=" * 50)
    print("MongoDB setup successful!")
    print("=" * 50)


if __name__ == "__main__":
    main()