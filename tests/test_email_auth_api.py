"""
Email/Password Authentication API Tests
Tests the new email/password auth system alongside existing Google OAuth.
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestRegisterEndpoint:
    """Tests for POST /api/auth/register"""

    def test_register_success(self):
        """Register with valid email/password should return user and token"""
        unique_email = f"test_register_{uuid.uuid4().hex[:8]}@ucan.cl"
        payload = {
            "email": unique_email,
            "password": "test123456",
            "name": "Test Register User"
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "user" in data, "Response should contain 'user'"
        assert "token" in data, "Response should contain 'token'"
        
        # Verify user data
        user = data["user"]
        assert user["email"] == unique_email, "Email should match"
        assert user["name"] == "Test Register User", "Name should match"
        assert "user_id" in user, "User should have user_id"
        assert user["role"] == "client", "Default role should be 'client'"
        
        # Verify token is a non-empty string
        assert isinstance(data["token"], str), "Token should be string"
        assert len(data["token"]) > 0, "Token should not be empty"
        
        # CRITICAL: hashed_password should NOT be in response
        assert "hashed_password" not in user, "hashed_password should NOT be returned"
        assert "hashed_password" not in data, "hashed_password should NOT be in response"

    def test_register_duplicate_email(self):
        """Register with existing email should return 400"""
        unique_email = f"test_dup_{uuid.uuid4().hex[:8]}@ucan.cl"
        payload = {
            "email": unique_email,
            "password": "test123456",
            "name": "First User"
        }
        
        # First registration
        response1 = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        assert response1.status_code == 200, "First registration should succeed"
        
        # Second registration with same email
        response2 = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        assert response2.status_code == 400, f"Duplicate email should return 400, got {response2.status_code}"
        
        data = response2.json()
        assert "detail" in data, "Error response should have 'detail'"
        # Spanish error message
        assert "correo" in data["detail"].lower() or "registrado" in data["detail"].lower(), \
            f"Error should mention email already registered: {data['detail']}"

    def test_register_short_password(self):
        """Register with password < 6 chars should return 400"""
        unique_email = f"test_short_{uuid.uuid4().hex[:8]}@ucan.cl"
        payload = {
            "email": unique_email,
            "password": "12345",  # Only 5 chars
            "name": "Short Pass User"
        }
        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        
        assert response.status_code == 400, f"Short password should return 400, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Error response should have 'detail'"
        # Spanish error about 6 characters
        assert "6" in data["detail"] or "caracteres" in data["detail"].lower(), \
            f"Error should mention 6 characters minimum: {data['detail']}"

    def test_register_missing_fields(self):
        """Register with missing fields should return 422"""
        # Missing name
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": "missing@test.com",
            "password": "test123456"
        })
        assert response.status_code == 422, f"Missing name should return 422, got {response.status_code}"
        
        # Missing email
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "password": "test123456",
            "name": "No Email"
        })
        assert response.status_code == 422, f"Missing email should return 422, got {response.status_code}"
        
        # Missing password
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": "nopass@test.com",
            "name": "No Password"
        })
        assert response.status_code == 422, f"Missing password should return 422, got {response.status_code}"


class TestLoginEndpoint:
    """Tests for POST /api/auth/login"""

    @pytest.fixture(autouse=True)
    def setup_test_user(self):
        """Create a test user for login tests"""
        self.test_email = f"test_login_{uuid.uuid4().hex[:8]}@ucan.cl"
        self.test_password = "test123456"
        self.test_name = "Test Login User"
        
        # Register the test user
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": self.test_email,
            "password": self.test_password,
            "name": self.test_name
        })
        assert response.status_code == 200, f"Setup failed to create user: {response.text}"

    def test_login_success(self):
        """Login with valid credentials should return user and token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.test_email,
            "password": self.test_password
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "user" in data, "Response should contain 'user'"
        assert "token" in data, "Response should contain 'token'"
        
        # Verify user data
        user = data["user"]
        assert user["email"] == self.test_email, "Email should match"
        assert user["name"] == self.test_name, "Name should match"
        
        # Verify token
        assert isinstance(data["token"], str), "Token should be string"
        assert len(data["token"]) > 0, "Token should not be empty"
        
        # CRITICAL: hashed_password should NOT be in response
        assert "hashed_password" not in user, "hashed_password should NOT be returned"
        assert "hashed_password" not in data, "hashed_password should NOT be in response"

    def test_login_wrong_password(self):
        """Login with wrong password should return 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.test_email,
            "password": "wrongpassword123"
        })
        
        assert response.status_code == 401, f"Wrong password should return 401, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Error response should have 'detail'"
        # Spanish error
        assert "correo" in data["detail"].lower() or "contraseña" in data["detail"].lower(), \
            f"Error should mention credentials: {data['detail']}"

    def test_login_nonexistent_email(self):
        """Login with non-existent email should return 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": f"nonexistent_{uuid.uuid4().hex}@test.com",
            "password": "anypassword123"
        })
        
        assert response.status_code == 401, f"Nonexistent email should return 401, got {response.status_code}"

    def test_login_missing_fields(self):
        """Login with missing fields should return 422"""
        # Missing password
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.test_email
        })
        assert response.status_code == 422, f"Missing password should return 422, got {response.status_code}"
        
        # Missing email
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "password": self.test_password
        })
        assert response.status_code == 422, f"Missing email should return 422, got {response.status_code}"


class TestGetMeEndpoint:
    """Tests for GET /api/auth/me with JWT token"""

    def test_get_me_with_jwt_token(self):
        """GET /api/auth/me with valid JWT token should return user"""
        # First register a user
        unique_email = f"test_me_{uuid.uuid4().hex[:8]}@ucan.cl"
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test Me User"
        })
        assert register_response.status_code == 200, f"Register failed: {register_response.text}"
        token = register_response.json()["token"]
        
        # Get current user with JWT
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        user = response.json()
        
        assert user["email"] == unique_email, "Email should match"
        assert user["name"] == "Test Me User", "Name should match"
        assert "has_subscription" in user, "Should include has_subscription"
        
        # CRITICAL: hashed_password should NOT be in response
        assert "hashed_password" not in user, "hashed_password should NOT be returned"

    def test_get_me_no_token(self):
        """GET /api/auth/me without token should return 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, f"No token should return 401, got {response.status_code}"

    def test_get_me_invalid_token(self):
        """GET /api/auth/me with invalid token should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401, f"Invalid token should return 401, got {response.status_code}"


class TestLogoutEndpoint:
    """Tests for POST /api/auth/logout"""

    def test_logout_success(self):
        """Logout should return success message"""
        response = requests.post(f"{BASE_URL}/api/auth/logout")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, "Response should contain 'message'"

    def test_logout_with_jwt_user(self):
        """Logout for JWT user should work"""
        # Register and get token
        unique_email = f"test_logout_{uuid.uuid4().hex[:8]}@ucan.cl"
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test Logout User"
        })
        token = register_response.json()["token"]
        
        # Logout with JWT in header
        response = requests.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


class TestEndToEndAuthFlow:
    """End-to-end authentication flow tests"""

    def test_full_register_login_flow(self):
        """Test complete flow: register -> login -> get me"""
        unique_email = f"test_e2e_{uuid.uuid4().hex[:8]}@ucan.cl"
        password = "test123456"
        name = "E2E Test User"
        
        # Step 1: Register
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "name": name
        })
        assert register_response.status_code == 200, f"Register failed: {register_response.text}"
        register_data = register_response.json()
        assert "token" in register_data
        
        # Step 2: Login with same credentials
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": unique_email,
            "password": password
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        login_data = login_response.json()
        login_token = login_data["token"]
        
        # Step 3: Get me with login token
        me_response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {login_token}"}
        )
        assert me_response.status_code == 200, f"Get me failed: {me_response.text}"
        me_data = me_response.json()
        
        assert me_data["email"] == unique_email, "Email should match"
        assert me_data["name"] == name, "Name should match"

    def test_provided_credentials(self):
        """Test with provided test credentials"""
        test_email = "testflow@ucan.cl"
        test_password = "test123456"
        test_name = "Test Flow User"
        
        # Try to register (may fail if exists)
        register_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": test_password,
            "name": test_name
        })
        
        if register_response.status_code == 200:
            print(f"Created test user: {test_email}")
        else:
            print(f"Test user may already exist: {register_response.json()}")
        
        # Login should work
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": test_email,
            "password": test_password
        })
        
        assert login_response.status_code == 200, f"Login failed for test user: {login_response.text}"
        data = login_response.json()
        assert "token" in data
        assert data["user"]["email"] == test_email


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
