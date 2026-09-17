from pymongo import MongoClient
from pymongo.database import Database

from supportcommander.core.config import get_settings

settings = get_settings()

client = MongoClient(
    settings.mongo_uri,
    serverSelectionTimeoutMS=5000,
)

def get_database() -> Database:
    return client[settings.mongo_db]

def ping_database() -> bool:
    client.admin.command("ping")
    return True
    
def close_database_connection() -> None:
    client.close()