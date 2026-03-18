"""
Test suite for branding cleanup - verifying U-CAN/pet terminology replaced with SeniorAdvisor/senior care
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBackendAPIs:
    """Test basic backend API functionality after branding changes"""
    
    def test_login_endpoint_works(self):
        """POST /api/auth/login - Admin can still login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@senioradvisor.cl",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        print(f"PASS: Admin login works, got token: {data['token'][:20]}...")
    
    def test_providers_endpoint_works(self):
        """GET /api/providers - Returns list of providers"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200, f"Providers fetch failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"PASS: Providers endpoint works, found {len(data)} providers")
    
    def test_register_provider_endpoint_exists(self):
        """POST /api/auth/register-provider - Endpoint exists and returns expected error for duplicate"""
        # Test with an existing email to verify endpoint works
        response = requests.post(f"{BASE_URL}/api/auth/register-provider", json={
            "business_name": "Test Residencia",
            "email": "admin@senioradvisor.cl",  # This email already exists
            "password": "test123456"
        })
        # Should return 400 because email exists, not 404 (endpoint missing)
        assert response.status_code == 400, f"Expected 400 for duplicate email, got {response.status_code}"
        data = response.json()
        assert "ya está registrado" in data.get("detail", ""), f"Expected 'ya está registrado' error message"
        print("PASS: register-provider endpoint works correctly")
    
    def test_register_provider_creates_pending_provider(self):
        """POST /api/auth/register-provider - Creates provider with approved=False"""
        import uuid
        test_email = f"TEST_branding_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register-provider", json={
            "business_name": "Test Residencia Branding",
            "email": test_email,
            "password": "test123456",
            "phone": "912345678",
            "comuna": "Providencia"
        })
        assert response.status_code == 200, f"Registration failed: {response.text}"
        data = response.json()
        assert data.get("status") == "pending_approval", f"Expected pending_approval status"
        assert "provider_id" in data, "provider_id not in response"
        print(f"PASS: Provider registration creates pending provider: {data['provider_id']}")


class TestBrandingInResponses:
    """Test that API responses use correct branding"""
    
    def test_register_provider_success_message(self):
        """Registration success message uses correct branding"""
        import uuid
        test_email = f"TEST_msg_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register-provider", json={
            "business_name": "Test Residencia Message",
            "email": test_email,
            "password": "test123456"
        })
        assert response.status_code == 200
        data = response.json()
        message = data.get("message", "")
        
        # Check message uses senior care terminology
        assert "residencia" in message.lower(), f"Message should mention 'residencia': {message}"
        assert "administrador" in message.lower(), f"Message should mention 'administrador': {message}"
        
        # Check message doesn't have old branding
        assert "u-can" not in message.lower(), f"Message should not contain 'U-CAN': {message}"
        assert "mascota" not in message.lower(), f"Message should not contain 'mascota': {message}"
        print(f"PASS: Registration message uses correct branding: {message[:50]}...")


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Clean up test data after all tests"""
    yield
    # After tests, we could clean up TEST_ prefixed users but that requires admin token
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
