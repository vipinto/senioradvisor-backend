"""
SeniorAdvisor Core API Tests
Tests for main functionality: providers list, provider details, auth, search by category
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://image-carousel-13.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_USER_EMAIL = "demo@senioradvisor.cl"
TEST_USER_PASSWORD = "demo123"


class TestHealthCheck:
    """Health check tests"""
    
    def test_health_endpoint(self):
        """API health check should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "SeniorAdvisor"
        print("✓ Health check passed")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success_demo_user(self):
        """Login with demo user credentials should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "token" in data, "Missing token in response"
        assert "user" in data, "Missing user in response"
        assert data["user"]["email"] == TEST_USER_EMAIL
        assert len(data["token"]) > 0
        print(f"✓ Login successful for {TEST_USER_EMAIL}")
    
    def test_login_invalid_credentials(self):
        """Login with invalid credentials should return 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")
    
    def test_auth_me_without_token(self):
        """GET /api/auth/me without token should return 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ Auth/me correctly requires authentication")
    
    def test_auth_me_with_valid_token(self):
        """GET /api/auth/me with valid token should return user data"""
        # First login to get token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Then get user data
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == TEST_USER_EMAIL
        assert "user_id" in data
        print("✓ Auth/me returns user data correctly")


class TestProvidersAPI:
    """Providers endpoint tests"""
    
    def test_get_providers_list(self):
        """GET /api/providers should return list of providers"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        
        assert isinstance(providers, list)
        assert len(providers) > 0, "Expected at least one provider"
        print(f"✓ Found {len(providers)} providers")
        
        # Validate provider structure
        provider = providers[0]
        assert "provider_id" in provider, "Missing provider_id"
        assert "business_name" in provider, "Missing business_name"
        assert "comuna" in provider, "Missing comuna"
        assert "services" in provider, "Missing services"
        print("✓ Provider structure is correct")
    
    def test_get_single_provider(self):
        """GET /api/providers/{providerId} should return provider details"""
        # First get a provider ID
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        assert len(providers) > 0
        
        provider_id = providers[0]["provider_id"]
        
        # Get single provider
        response = requests.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert response.status_code == 200
        provider = response.json()
        
        # Validate structure for provider profile page
        assert provider["provider_id"] == provider_id
        assert "business_name" in provider
        assert "description" in provider
        assert "services" in provider
        assert "reviews" in provider
        assert "rating" in provider
        assert "viewer_has_subscription" in provider  # For contact form visibility
        print(f"✓ Provider details returned for {provider['business_name']}")
    
    def test_provider_not_found(self):
        """GET /api/providers/{invalid_id} should return 404"""
        response = requests.get(f"{BASE_URL}/api/providers/invalid-provider-id")
        assert response.status_code == 404
        print("✓ Invalid provider ID correctly returns 404")


class TestProviderSearch:
    """Provider search and filter tests - Senior care categories"""
    
    def test_search_by_residencias(self):
        """Search providers by 'residencias' category"""
        response = requests.get(f"{BASE_URL}/api/providers", params={
            "service_type": "residencias"
        })
        assert response.status_code == 200
        providers = response.json()
        
        # Verify all returned providers have residencias service
        for provider in providers:
            services = provider.get("services", [])
            service_types = [s["service_type"] for s in services]
            assert "residencias" in service_types, f"Provider {provider['business_name']} doesn't have residencias service"
        
        print(f"✓ Found {len(providers)} providers with 'residencias' service")
    
    def test_search_by_cuidado_domicilio(self):
        """Search providers by 'cuidado-domicilio' category"""
        response = requests.get(f"{BASE_URL}/api/providers", params={
            "service_type": "cuidado-domicilio"
        })
        assert response.status_code == 200
        providers = response.json()
        
        for provider in providers:
            services = provider.get("services", [])
            service_types = [s["service_type"] for s in services]
            assert "cuidado-domicilio" in service_types, f"Provider {provider['business_name']} doesn't have cuidado-domicilio service"
        
        print(f"✓ Found {len(providers)} providers with 'cuidado-domicilio' service")
    
    def test_search_by_salud_mental(self):
        """Search providers by 'salud-mental' category"""
        response = requests.get(f"{BASE_URL}/api/providers", params={
            "service_type": "salud-mental"
        })
        assert response.status_code == 200
        providers = response.json()
        
        for provider in providers:
            services = provider.get("services", [])
            service_types = [s["service_type"] for s in services]
            assert "salud-mental" in service_types, f"Provider {provider['business_name']} doesn't have salud-mental service"
        
        print(f"✓ Found {len(providers)} providers with 'salud-mental' service")
    
    def test_search_by_comuna(self):
        """Search providers by comuna"""
        response = requests.get(f"{BASE_URL}/api/providers", params={
            "comuna": "Las Condes"
        })
        assert response.status_code == 200
        providers = response.json()
        print(f"✓ Found {len(providers)} providers in 'Las Condes'")


class TestProviderProfileContent:
    """Tests for provider profile page content"""
    
    def test_provider_has_contact_info_for_logged_in_user(self):
        """Provider profile should show contact info for logged in users"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Get provider list
        response = requests.get(f"{BASE_URL}/api/providers")
        providers = response.json()
        provider_id = providers[0]["provider_id"]
        
        # Get provider details as logged in user
        response = requests.get(
            f"{BASE_URL}/api/providers/{provider_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        provider = response.json()
        
        # Check that contact info is available (not paywalled)
        assert provider["viewer_has_subscription"] == True, "Logged in users should have subscription access"
        assert provider["contact_blocked"] == False, "Contact should not be blocked for logged in users"
        print("✓ Provider contact info available for logged in users (no paywall)")
    
    def test_provider_profile_has_all_sections(self):
        """Provider profile should have all required sections for rendering"""
        # Get provider list
        response = requests.get(f"{BASE_URL}/api/providers")
        providers = response.json()
        provider_id = providers[0]["provider_id"]
        
        # Get provider details
        response = requests.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert response.status_code == 200
        provider = response.json()
        
        # Validate all sections exist for ProviderProfile.jsx
        required_fields = [
            "provider_id", "business_name", "description", "rating",
            "services", "reviews", "comuna"
        ]
        
        for field in required_fields:
            assert field in provider, f"Missing required field: {field}"
        
        print("✓ Provider profile has all required sections")


class TestServiceTypes:
    """Verify senior care service types are correctly configured"""
    
    def test_provider_services_have_correct_types(self):
        """All provider services should have valid senior care types"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        
        valid_service_types = ["residencias", "cuidado-domicilio", "salud-mental"]
        
        for provider in providers:
            for service in provider.get("services", []):
                service_type = service.get("service_type")
                assert service_type in valid_service_types, \
                    f"Invalid service type '{service_type}' in provider {provider['business_name']}"
        
        print(f"✓ All {len(providers)} providers have valid senior care service types")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
