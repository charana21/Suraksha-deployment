# #!/usr/bin/env python3
# """
# Create Admin User Script

# Run this script to create the first admin user for CrowdVision.
# Can also be used to create additional users.

# Usage:
#     python scripts/create_admin.py

#     # Or with arguments:
#     python scripts/create_admin.py --username admin --password secret123 --role admin
# """

# import asyncio
# import argparse
# import getpass
# import sys
# import os

# # Add project root to path
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from api.auth import UserCreate, UserManager, hash_password
# from db.mongodb import get_database, close_mongo_connection, connect_to_mongo
# from config.config import get_settings


# async def check_existing_users():
#     """Check if any users exist"""
#     try:
#         exists = await UserManager.user_exists()
#         return exists
#     except Exception as e:
#         print(f"Error checking users: {e}")
#         return False


# async def create_user(username: str, password: str, role: str, full_name: str = None):
#     """Create a user in the database"""
#     try:
#         user_data = UserCreate(
#             username=username,
#             password=password,
#             role=role,
#             full_name=full_name
#         )

#         user = await UserManager.create_user(user_data)
#         return user

#     except Exception as e:
#         print(f"Error creating user: {e}")
#         return None


# def get_password_interactive() -> str:
#     """Get password interactively with confirmation"""
#     while True:
#         password = getpass.getpass("Enter password (min 6 chars): ")
#         if len(password) < 6:
#             print("Password must be at least 6 characters")
#             continue

#         confirm = getpass.getpass("Confirm password: ")
#         if password != confirm:
#             print("Passwords don't match. Try again.")
#             continue

#         return password


# async def main():
#     parser = argparse.ArgumentParser(description="Create CrowdVision user")
#     parser.add_argument("--username", "-u", help="Username")
#     parser.add_argument("--password", "-p", help="Password (will prompt if not provided)")
#     parser.add_argument("--role", "-r", choices=["admin", "operator", "viewer"],
#                         default="admin", help="User role (default: admin)")
#     parser.add_argument("--name", "-n", help="Full name (optional)")
#     parser.add_argument("--force", "-f", action="store_true",
#                         help="Create user even if users already exist")

#     args = parser.parse_args()

#     print("\n" + "="*50)
#     print("CrowdVision User Creation")
#     print("="*50 + "\n")

#     # Connect to MongoDB
#     await connect_to_mongo(get_settings())

#     # Check if users already exist
#     has_users = await check_existing_users()
#     if has_users and not args.force:
#         print("Users already exist in the database.")
#         print("Use --force to create additional users.\n")

#         # Show existing users
#         users = await UserManager.list_users()
#         print("Existing users:")
#         for user in users:
#             print(f"  - {user.username} ({user.role})")
#         print()

#         response = input("Create another user? (y/n): ").lower().strip()
#         if response != 'y':
#             print("Aborted.")
#             await close_mongo_connection()
#             return

#     # Get username
#     username = args.username
#     if not username:
#         username = input("Username: ").strip()
#         if not username:
#             print("Username is required")
#             await close_mongo_connection()
#             return

#     # Check if username exists
#     existing = await UserManager.get_user(username)
#     if existing:
#         print(f"User '{username}' already exists!")
#         await close_mongo_connection()
#         return

#     # Get password
#     password = args.password
#     if not password:
#         password = get_password_interactive()

#     # Get role
#     role = args.role
#     if not args.username:  # Interactive mode
#         print("\nRoles:")
#         print("  1. admin    - Full access (create users, manage system)")
#         print("  2. operator - Manage streams, view all data")
#         print("  3. viewer   - Read-only access")
#         role_choice = input(f"Select role [1-3] (default: 1): ").strip()
#         if role_choice == "2":
#             role = "operator"
#         elif role_choice == "3":
#             role = "viewer"
#         else:
#             role = "admin"

#     # Get full name
#     full_name = args.name
#     if not full_name and not args.username:
#         full_name = input("Full name (optional): ").strip() or None

#     # Confirm
#     print(f"\nCreating user:")
#     print(f"  Username: {username}")
#     print(f"  Role: {role}")
#     print(f"  Full name: {full_name or '(not set)'}")

#     if not args.username:  # Interactive mode
#         confirm = input("\nProceed? (y/n): ").lower().strip()
#         if confirm != 'y':
#             print("Aborted.")
#             await close_mongo_connection()
#             return

#     # Create user
#     user = await create_user(username, password, role, full_name)

#     if user:
#         print(f"\n✓ User '{username}' created successfully!")
#         print(f"  Role: {role}")
#         print(f"  Created: {user.created_at}")

#         if role == "admin":
#             print("\n  This user has full admin access.")
#     else:
#         print("\n✗ Failed to create user")

#     await close_mongo_connection()


# if __name__ == "__main__":
#     asyncio.run(main())
