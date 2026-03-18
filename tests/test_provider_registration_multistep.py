"""
Test suite for multi-step provider registration feature.
Tests the public /api/auth/register-provider endpoint and admin approval flow.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProviderRegistration:
    """Tests for public provider registration endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data with unique identifiers"""
        self.unique_id = uuid.uuid4().hex[:8]
        self.test_email = f"TEST_provider_{self.unique_id}@senioradvisor.cl"
        self.admin_email = "admin@senioradvisor.cl"
        self.admin_password = "admin123"
        self.created_provider_id = None
    
    def get_admin_token(self):
        """Get admin JWT token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    # Test 1: Register provider with valid data
    def test_register_provider_success(self):
        """POST /api/auth/register-provider creates user with role 'provider' and provider with approved=False"""
        payload = {
            "business_name": f"TEST Residencia {self.unique_id}",
            "email": self.test_email,
            "password": "test123456",
            "phone": "+56912345678",
            "address": "Av. Test 123",
            "comuna": "Las Condes",
            "region": "Región Metropolitana",
            "website": "https://test.cl",
            "facebook": "https://facebook.com/test",
            "instagram": "https://instagram.com/test",
            "services": [
                {"service_type": "residencias", "price_from": 1500000, "description": "Servicio completo"},
                {"service_type": "cuidado-domicilio", "price_from": 50000, "description": "Por hora"}
            ],
            "amenities": ["geriatria", "enfermeria", "wifi", "jardin"]
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "provider_id" in data, "Response should contain provider_id"
        assert data["status"] == "pending_approval", "Status should be pending_approval"
        assert "message" in data, "Response should contain message"
        
        self.created_provider_id = data["provider_id"]
        print(f"✓ Provider registered successfully: {self.created_provider_id}")
        
        return data["provider_id"]
    
    # Test 2: Duplicate email returns 400
    def test_register_provider_duplicate_email(self):
        """Duplicate email registration returns 400 error"""
        # First registration
        payload = {
            "business_name": f"TEST Residencia {self.unique_id}",
            "email": f"TEST_dup_{self.unique_id}@senioradvisor.cl",
            "password": "test123456"
        }
        
        response1 = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        assert response1.status_code == 200, f"First registration failed: {response1.text}"
        
        # Second registration with same email
        response2 = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        
        # Status assertion - should be 400
        assert response2.status_code == 400, f"Expected 400 for duplicate, got {response2.status_code}"
        
        # Data assertion - should contain error message
        data = response2.json()
        assert "detail" in data, "Error response should contain detail"
        assert "registrado" in data["detail"].lower(), f"Error message should mention email already registered: {data}"
        print("✓ Duplicate email correctly rejected with 400")
    
    # Test 3: Short password returns 400
    def test_register_provider_short_password(self):
        """Short password (<6 chars) returns 400 error"""
        payload = {
            "business_name": "TEST Short Password",
            "email": f"TEST_shortpwd_{self.unique_id}@senioradvisor.cl",
            "password": "abc"  # Less than 6 characters
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        
        # Status assertion - should be 400
        assert response.status_code == 400, f"Expected 400 for short password, got {response.status_code}"
        
        # Data assertion
        data = response.json()
        assert "detail" in data, "Error response should contain detail"
        assert "6" in data["detail"], f"Error message should mention 6 characters: {data}"
        print("✓ Short password correctly rejected with 400")
    
    # Test 4: Empty business name returns 400
    def test_register_provider_empty_business_name(self):
        """Empty business name returns 400 error"""
        payload = {
            "business_name": "",
            "email": f"TEST_empty_{self.unique_id}@senioradvisor.cl",
            "password": "test123456"
        }
        
        response = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        
        # Status assertion - should be 400
        assert response.status_code == 400, f"Expected 400 for empty name, got {response.status_code}"
        print("✓ Empty business name correctly rejected with 400")


class TestProviderPendingApproval:
    """Tests for admin pending providers endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.unique_id = uuid.uuid4().hex[:8]
        self.admin_email = "admin@senioradvisor.cl"
        self.admin_password = "admin123"
    
    def get_admin_token(self):
        """Get admin JWT token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    # Test 5: Provider appears in pending list
    def test_provider_in_pending_list(self):
        """Provider appears in GET /api/admin/providers/pending (admin auth required)"""
        # First create a new provider
        test_email = f"TEST_pending_{self.unique_id}@senioradvisor.cl"
        payload = {
            "business_name": f"TEST Pending Provider {self.unique_id}",
            "email": test_email,
            "password": "test123456",
            "comuna": "Providencia"
        }
        
        reg_response = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        assert reg_response.status_code == 200, f"Registration failed: {reg_response.text}"
        provider_id = reg_response.json()["provider_id"]
        
        # Get admin token
        token = self.get_admin_token()
        assert token is not None, "Failed to get admin token"
        
        # Check pending providers
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/admin/providers/pending", headers=headers)
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Data assertion - our provider should be in the list
        providers = response.json()
        assert isinstance(providers, list), "Response should be a list"
        
        provider_ids = [p["provider_id"] for p in providers]
        assert provider_id in provider_ids, f"Provider {provider_id} should be in pending list"
        print(f"✓ Provider {provider_id} found in pending list")
    
    # Test 6: Pending endpoint requires admin auth
    def test_pending_requires_auth(self):
        """GET /api/admin/providers/pending requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/providers/pending")
        
        # Status assertion - should be 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Pending endpoint correctly requires authentication")


class TestProviderPublicSearch:
    """Tests for public provider search"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.unique_id = uuid.uuid4().hex[:8]
    
    # Test 7: Pending provider NOT in public search
    def test_pending_provider_not_in_public_search(self):
        """Provider does NOT appear in public search GET /api/providers (because approved=False)"""
        # Create a new provider (will be pending)
        test_email = f"TEST_nosearch_{self.unique_id}@senioradvisor.cl"
        payload = {
            "business_name": f"TEST NoSearch Provider {self.unique_id}",
            "email": test_email,
            "password": "test123456",
            "comuna": "Santiago"
        }
        
        reg_response = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        assert reg_response.status_code == 200, f"Registration failed: {reg_response.text}"
        provider_id = reg_response.json()["provider_id"]
        
        # Search public providers
        response = requests.get(f"{BASE_URL}/api/providers?limit=500")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Data assertion - pending provider should NOT be in results
        providers = response.json()
        provider_ids = [p["provider_id"] for p in providers]
        
        assert provider_id not in provider_ids, f"Pending provider {provider_id} should NOT be in public search"
        print(f"✓ Pending provider {provider_id} correctly hidden from public search")


class TestAdminProviderApproval:
    """Tests for admin approval flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.unique_id = uuid.uuid4().hex[:8]
        self.admin_email = "admin@senioradvisor.cl"
        self.admin_password = "admin123"
    
    def get_admin_token(self):
        """Get admin JWT token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": self.admin_email,
            "password": self.admin_password
        })
        if response.status_code == 200:
            return response.json().get("token")
        return None
    
    # Test 8: Admin can approve provider
    def test_admin_approve_provider(self):
        """Admin can approve the provider via POST /api/admin/providers/{id}/approve"""
        # Create a new provider
        test_email = f"TEST_approve_{self.unique_id}@senioradvisor.cl"
        payload = {
            "business_name": f"TEST Approve Provider {self.unique_id}",
            "email": test_email,
            "password": "test123456",
            "comuna": "Las Condes"
        }
        
        reg_response = requests.post(f"{BASE_URL}/api/auth/register-provider", json=payload)
        assert reg_response.status_code == 200, f"Registration failed: {reg_response.text}"
        provider_id = reg_response.json()["provider_id"]
        
        # Get admin token
        token = self.get_admin_token()
        assert token is not None, "Failed to get admin token"
        
        # Approve the provider
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/{provider_id}/approve",
            headers=headers
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertion
        data = response.json()
        assert "message" in data, "Response should contain message"
        print(f"✓ Provider {provider_id} approved successfully")
        
        # Verify provider now appears in public search
        search_response = requests.get(f"{BASE_URL}/api/providers?limit=500")
        assert search_response.status_code == 200
        
        providers = search_response.json()
        provider_ids = [p["provider_id"] for p in providers]
        
        assert provider_id in provider_ids, f"Approved provider {provider_id} should now appear in public search"
        print(f"✓ Approved provider {provider_id} now visible in public search")
    
    # Test 9: Approve requires admin auth
    def test_approve_requires_admin(self):
        """POST /api/admin/providers/{id}/approve requires admin authentication"""
        response = requests.post(f"{BASE_URL}/api/admin/providers/fake_id/approve")
        
        # Status assertion - should be 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Approve endpoint correctly requires admin authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
