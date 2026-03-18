"""
Test Google OAuth Redirect Flow (Safari-compatible authorization code flow)
Tests the changes from popup-based to redirect-based Google OAuth

Features tested:
- POST /api/auth/google with code+redirect_uri (new redirect flow)
- POST /api/auth/google with credential (legacy popup flow - still supported)
- POST /api/auth/google with invalid/fake code (expected error)
- POST /api/auth/login with email/password (regression test)
- POST /api/auth/register with email/password (regression test)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestGoogleOAuthRedirectFlow:
    """Test the new redirect-based Google OAuth flow"""
    
    def test_api_health(self):
        """Verify API is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ API health check passed")
    
    def test_google_auth_with_code_and_redirect_uri(self):
        """Test POST /api/auth/google with code+redirect_uri (new redirect flow)
        
        Expected: Returns 401 with 'Error al verificar con Google' because
        we're sending a fake code. This is expected behavior.
        """
        response = requests.post(
            f"{BASE_URL}/api/auth/google",
            json={
                "code": "fake_auth_code_12345",
                "redirect_uri": "https://image-carousel-13.preview.emergentagent.com/auth/google/callback"
            },
            headers={"Content-Type": "application/json"}
        )
        
        # With a fake code, Google will reject it - this is EXPECTED
        assert response.status_code == 401
        data = response.json()
        assert "Error al verificar con Google" in data.get("detail", "")
        print("✓ Google auth with code+redirect_uri correctly rejects fake code (401)")
    
    def test_google_auth_with_credential_legacy(self):
        """Test POST /api/auth/google with credential only (legacy popup flow)
        
        Expected: Returns 401 with 'Token de Google inválido' because
        we're sending a fake credential. This verifies the legacy path still works.
        """
        response = requests.post(
            f"{BASE_URL}/api/auth/google",
            json={
                "credential": "fake_id_token_eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
            },
            headers={"Content-Type": "application/json"}
        )
        
        # With a fake credential, Google will reject it - this is EXPECTED
        assert response.status_code == 401
        data = response.json()
        assert "Token de Google inválido" in data.get("detail", "")
        print("✓ Google auth with credential (legacy) correctly rejects fake token (401)")
    
    def test_google_auth_missing_params(self):
        """Test POST /api/auth/google with no credential or code
        
        Expected: Returns 400 with 'Se requiere credential o code'
        """
        response = requests.post(
            f"{BASE_URL}/api/auth/google",
            json={},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Se requiere credential o code" in data.get("detail", "")
        print("✓ Google auth correctly requires credential or code (400)")
    
    def test_google_auth_code_without_redirect_uri(self):
        """Test POST /api/auth/google with code but no redirect_uri
        
        Expected: Should work since code alone triggers the redirect flow
        but redirect_uri is needed for token exchange.
        Actually, checking the code - if only code is provided without redirect_uri,
        it should fall through to the else branch and return 400.
        """
        response = requests.post(
            f"{BASE_URL}/api/auth/google",
            json={
                "code": "fake_auth_code_12345"
            },
            headers={"Content-Type": "application/json"}
        )
        
        # The code path requires redirect_uri, so this should return 400
        assert response.status_code == 400
        data = response.json()
        assert "Se requiere credential o code" in data.get("detail", "")
        print("✓ Google auth correctly requires redirect_uri with code (400)")


class TestEmailAuthRegression:
    """Regression tests for email/password authentication"""
    
    def test_email_login_success(self):
        """Test POST /api/auth/login with valid credentials (admin@test.com / password123)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "admin@test.com",
                "password": "password123"
            },
            headers={"Content-Type": "application/json"}
        )
        
        # Check if user exists - if not, we need to try different test credentials
        if response.status_code == 401:
            # Try admin@ucan.cl / admin123 from iteration 10
            response = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={
                    "email": "admin@ucan.cl",
                    "password": "admin123"
                },
                headers={"Content-Type": "application/json"}
            )
        
        assert response.status_code == 200, f"Login failed with {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "token" in data, "Response missing token"
        assert "user" in data, "Response missing user"
        assert isinstance(data["token"], str) and len(data["token"]) > 0, "Token is empty"
        assert "user_id" in data["user"], "User missing user_id"
        assert "email" in data["user"], "User missing email"
        
        print(f"✓ Email login successful for {data['user']['email']}")
        return data["token"]
    
    def test_email_login_invalid_credentials(self):
        """Test POST /api/auth/login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "nonexistent@test.com",
                "password": "wrongpassword"
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Correo o contraseña incorrectos" in data["detail"]
        print("✓ Email login correctly rejects invalid credentials (401)")
    
    def test_email_register_new_user(self):
        """Test POST /api/auth/register with new user"""
        unique_email = f"test_oauth_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": unique_email,
                "password": "testpass123",
                "name": "Test OAuth User"
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "token" in data, "Response missing token"
        assert "user" in data, "Response missing user"
        assert data["user"]["email"] == unique_email
        assert data["user"]["name"] == "Test OAuth User"
        
        print(f"✓ Email registration successful for {unique_email}")
        return data["token"]
    
    def test_email_register_duplicate_email(self):
        """Test POST /api/auth/register with existing email"""
        # First create a user
        unique_email = f"test_dup_{uuid.uuid4().hex[:8]}@example.com"
        
        requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": unique_email,
                "password": "testpass123",
                "name": "First User"
            }
        )
        
        # Try to register again with same email
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": unique_email,
                "password": "anotherpass",
                "name": "Second User"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Este correo ya está registrado" in data.get("detail", "")
        print("✓ Email registration correctly rejects duplicate email (400)")
    
    def test_email_register_short_password(self):
        """Test POST /api/auth/register with password < 6 chars"""
        unique_email = f"test_short_{uuid.uuid4().hex[:8]}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": unique_email,
                "password": "12345",  # Only 5 chars
                "name": "Short Password User"
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "al menos 6 caracteres" in data.get("detail", "")
        print("✓ Email registration correctly rejects short password (400)")


class TestAuthMeEndpoint:
    """Test /api/auth/me endpoint with JWT token"""
    
    def test_auth_me_with_valid_token(self):
        """Test GET /api/auth/me with valid JWT token"""
        # First login to get a token
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "admin@ucan.cl",
                "password": "admin123"
            }
        )
        
        if login_response.status_code != 200:
            pytest.skip("Admin user not found, skipping auth/me test")
        
        token = login_response.json()["token"]
        
        # Test /auth/me with the token
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        assert data["email"] == "admin@ucan.cl"
        print(f"✓ GET /api/auth/me returned user: {data['email']}")
    
    def test_auth_me_without_token(self):
        """Test GET /api/auth/me without authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        
        assert response.status_code == 401
        print("✓ GET /api/auth/me correctly returns 401 without token")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
