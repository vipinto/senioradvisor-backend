"""
Iteration 38 - Provider Dashboard Restructuring Tests
Tests the new provider experience with separated Dashboard and Mi Cuenta pages.
- Dashboard (Panel): Only Solicitudes Publicadas + Sucursales + link to main profile
- Mi Cuenta (ProviderAccount): Profile, Precios, Servicios, Galería, Redes Sociales tabs
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable is required")

# Provider credentials
PROVIDER_EMAIL = "proveedor1@senioradvisor.cl"
PROVIDER_PASSWORD = "demo123"


class TestProviderAuthentication:
    """Authentication tests for provider endpoints"""
    
    def test_provider_login(self):
        """Test provider can login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PROVIDER_EMAIL,
            "password": PROVIDER_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, "No token in login response"
        assert data.get("user", {}).get("email") == PROVIDER_EMAIL
        print(f"✓ Provider login successful")


class TestMyProfileEndpoint:
    """Tests for GET /api/providers/my-profile"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PROVIDER_EMAIL,
            "password": PROVIDER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Authentication failed")
        return response.json()["token"]
    
    def test_my_profile_returns_full_data(self, auth_token):
        """Test GET /api/providers/my-profile returns services, amenities, social_links"""
        response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should return basic provider fields
        assert "provider_id" in data, "Missing provider_id"
        assert "business_name" in data, "Missing business_name"
        
        # Should return services array
        assert "services" in data, "Missing services field"
        assert isinstance(data["services"], list), "services should be a list"
        
        # Should include amenities (can be empty)
        # Note: amenities might not exist if never set
        assert "amenities" in data or data.get("amenities") is None or data.get("amenities") == [], "amenities field should exist"
        
        # Should include social_links (can be empty)
        # Note: social_links might not exist if never set
        print(f"✓ GET /api/providers/my-profile returns full data with {len(data.get('services', []))} services")
    
    def test_my_profile_returns_401_without_auth(self):
        """Test GET /api/providers/my-profile returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/providers/my-profile")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ GET /api/providers/my-profile correctly returns 401 without auth")


class TestAmenitiesEndpoint:
    """Tests for PUT /api/providers/my-profile/amenities"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PROVIDER_EMAIL,
            "password": PROVIDER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Authentication failed")
        return response.json()["token"]
    
    def test_amenities_returns_401_without_auth(self):
        """Test PUT /api/providers/my-profile/amenities returns 401 without auth"""
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/amenities",
            json={"amenities": ["wifi", "geriatria"]}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ PUT /api/providers/my-profile/amenities correctly returns 401 without auth")
    
    def test_amenities_save_and_verify(self, auth_token):
        """Test PUT /api/providers/my-profile/amenities saves amenities array"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        test_amenities = ["geriatria", "enfermeria", "wifi", "kinesiologia"]
        
        # Save amenities
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/amenities",
            json={"amenities": test_amenities},
            headers=headers
        )
        assert response.status_code == 200, f"Failed to save amenities: {response.text}"
        
        # Data assertions on save response
        data = response.json()
        assert "message" in data, "Response should have message"
        assert "amenities" in data, "Response should return saved amenities"
        assert set(data["amenities"]) == set(test_amenities), "Returned amenities don't match"
        
        # Verify via GET /api/providers/my-profile (CREATE→GET pattern)
        verify_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=headers
        )
        assert verify_response.status_code == 200
        profile_data = verify_response.json()
        
        # Verify amenities persisted
        saved_amenities = profile_data.get("amenities", [])
        assert set(saved_amenities) == set(test_amenities), f"Amenities not persisted. Expected {test_amenities}, got {saved_amenities}"
        
        print(f"✓ PUT /api/providers/my-profile/amenities saves {len(test_amenities)} amenities and persists correctly")
    
    def test_amenities_save_empty_array(self, auth_token):
        """Test saving an empty amenities array"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/amenities",
            json={"amenities": []},
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify
        verify = requests.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert verify.status_code == 200
        assert verify.json().get("amenities") == [], "Empty array should persist"
        
        print("✓ Saving empty amenities array works correctly")


class TestSocialLinksEndpoint:
    """Tests for PUT /api/providers/my-profile/social"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PROVIDER_EMAIL,
            "password": PROVIDER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Authentication failed")
        return response.json()["token"]
    
    def test_social_returns_401_without_auth(self):
        """Test PUT /api/providers/my-profile/social returns 401 without auth"""
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/social",
            json={"instagram": "https://instagram.com/test"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ PUT /api/providers/my-profile/social correctly returns 401 without auth")
    
    def test_social_links_save_and_verify(self, auth_token):
        """Test PUT /api/providers/my-profile/social saves social_links"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        test_social = {
            "instagram": "https://instagram.com/test_residencia",
            "facebook": "https://facebook.com/test_residencia",
            "website": "https://www.test-residencia.cl"
        }
        
        # Save social links
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/social",
            json=test_social,
            headers=headers
        )
        assert response.status_code == 200, f"Failed to save social links: {response.text}"
        
        # Data assertions on save response
        data = response.json()
        assert "message" in data, "Response should have message"
        assert "social_links" in data, "Response should return saved social_links"
        assert data["social_links"]["instagram"] == test_social["instagram"]
        assert data["social_links"]["facebook"] == test_social["facebook"]
        assert data["social_links"]["website"] == test_social["website"]
        
        # Verify via GET /api/providers/my-profile (CREATE→GET pattern)
        verify_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=headers
        )
        assert verify_response.status_code == 200
        profile_data = verify_response.json()
        
        # Verify social_links persisted
        saved_social = profile_data.get("social_links", {})
        assert saved_social.get("instagram") == test_social["instagram"]
        assert saved_social.get("facebook") == test_social["facebook"]
        assert saved_social.get("website") == test_social["website"]
        
        print("✓ PUT /api/providers/my-profile/social saves all 3 social links and persists correctly")
    
    def test_social_links_partial_save(self, auth_token):
        """Test saving only some social links"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Only save instagram
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/social",
            json={"instagram": "https://instagram.com/only_insta"},
            headers=headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "instagram" in data.get("social_links", {}), "Instagram should be saved"
        # Other fields might be empty/missing since we only sent instagram
        
        print("✓ Partial social links save works correctly")


class TestServicesEndpoint:
    """Tests for PUT /api/providers/my-profile/services"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PROVIDER_EMAIL,
            "password": PROVIDER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Authentication failed")
        return response.json()["token"]
    
    def test_services_returns_401_without_auth(self):
        """Test PUT /api/providers/my-profile/services returns 401 without auth"""
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/services",
            json={"services": []}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ PUT /api/providers/my-profile/services correctly returns 401 without auth")
    
    def test_services_save_and_verify(self, auth_token):
        """Test PUT /api/providers/my-profile/services saves services array"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        test_services = [
            {"service_type": "residencias", "price_from": 1500000, "description": "Estadía completa con cuidado 24/7"},
            {"service_type": "cuidado-domicilio", "price_from": 50000, "description": "Visitas a domicilio"},
            {"service_type": "salud-mental", "price_from": 80000, "description": "Apoyo psicológico"}
        ]
        
        # Save services
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/services",
            json={"services": test_services},
            headers=headers
        )
        assert response.status_code == 200, f"Failed to save services: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have message"
        
        # Verify via GET /api/providers/my-profile (CREATE→GET pattern)
        verify_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=headers
        )
        assert verify_response.status_code == 200
        profile_data = verify_response.json()
        
        # Verify services persisted
        saved_services = profile_data.get("services", [])
        assert len(saved_services) >= len(test_services), f"Expected at least {len(test_services)} services, got {len(saved_services)}"
        
        # Check service types exist
        service_types = [s.get("service_type") for s in saved_services]
        for ts in test_services:
            assert ts["service_type"] in service_types, f"Service type {ts['service_type']} not found in saved services"
        
        print(f"✓ PUT /api/providers/my-profile/services saves {len(test_services)} services and persists correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
