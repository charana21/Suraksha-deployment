import asyncio
import sys
import os
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.auth import UserManager
from db.mongodb import connect_to_mongo, close_mongo_connection
from config.config import get_settings

async def check_users():
    settings = get_settings()
    await connect_to_mongo(settings)
    
    users = await UserManager.list_users()
    print("\n--- Current Users in Database ---")
    if not users:
        print("No users found.")
    else:
        for user in users:
            print(f"Username: {user.username} | Role: {user.role} | Active: {user.is_active}")
    print("---------------------------------\n")
    
    await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(check_users())
