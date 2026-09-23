"""
Manual MongoDB index management.

Run explicitly when you want to apply/update indexes:
    python -m scripts.manage_indexes
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config.config import get_settings
from db.mongodb import MongoDB, create_indexes, close_mongo_connection

async def main() -> int:
    settings = get_settings()

    try:
        MongoDB.client = AsyncIOMotorClient(
            settings.mongodb_uri,
            maxPoolSize=settings.mongodb_max_pool_size,
            connectTimeoutMS=settings.mongodb_connect_timeout_ms,
            serverSelectionTimeoutMS=30000,
        )
        MongoDB.database = MongoDB.client[settings.mongodb_database]

        await MongoDB.client.admin.command("ping")
        print(f"[IndexManager] Connected to database: {settings.mongodb_database}")

        await create_indexes()
        print("[IndexManager] Manual index sync completed successfully")
        return 0

    except Exception as exc:
        print(f"[IndexManager] Index sync failed: {exc}")
        return 1

    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
