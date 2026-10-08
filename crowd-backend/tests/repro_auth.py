
# import os
# import sys
# # Add project root to sys.path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# # Set AUTH_ENABLED to true to test the failure case
# os.environ["AUTH_ENABLED"] = "True"

# from fastapi.testclient import TestClient
# from main import app
# from config.config import get_settings

# def test_auth_flow():
#     settings = get_settings()
#     print(f"Auth Enabled: {settings.auth_enabled}")
#     print(f"JWT Secret: {settings.jwt_secret}")

#     client = TestClient(app)

#     # 1. Login to get token
#     # We need a user first. verify_token is disabled for /auth/login so we can use it.
#     # But wait, we need a user in DB. 
#     # Let's mock the db or just try to use a fake token if we can't login?
#     # Actually, we can just generate a token using create_access_token from auth logic directly.
    
#     from api.auth import create_access_token
    
#     token = create_access_token({"sub": "testuser", "role": "admin"})
#     print(f"Generated Token: {token}")
    
#     # 2. Access /auth/me with Valid Token
#     headers = {"Authorization": f"Bearer {token}"}
#     response = client.get("/auth/me", headers=headers)
    
#     print(f"Response Status: {response.status_code}")
#     print(f"Response Body: {response.json()}")
    
#     if response.status_code == 401:
#         print("FAIL: Got 401 despite valid token")
#     elif response.status_code == 200:
#         print("SUCCESS: Auth worked")
#     elif response.status_code == 404:
#         print("partial success: Auth passed (user not found in db), but token verified")
#     else:
#         print(f"Other error: {response.status_code}")

# if __name__ == "__main__":
#     test_auth_flow()
