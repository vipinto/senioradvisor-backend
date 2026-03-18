"""
Iteration 33 - Test Residencia Creation Forms
Testing:
1. POST /api/admin/residencias/create - All fields stored correctly
2. PUT /api/providers/my-profile - Update profile with region, place_id, price_from
3. GET /api/providers - Search with service type filters
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminResidenciaCreate:
    """Test POST /api/admin/residencias/create endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin to get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@senioradvisor.cl",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        self.admin_token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def test_create_residencia_with_all_fields(self):
        """Test creating a residence with ALL the new fields"""
        unique_id = uuid.uuid4().hex[:8]
        test_email = f"test_residencia_{unique_id}@testsenior.cl"
        
        payload = {
            "business_name": f"Residencia Test Completa {unique_id}",
            "email": test_email,
            "phone": "+56912345678",
            "address": "Av. Test 123, Santiago",
            "region": "Región Metropolitana",
            "comuna": "Las Condes",
            "website": "https://www.testresidencia.cl",
            "facebook": "https://facebook.com/testresidencia",
            "instagram": "https://instagram.com/testresidencia",
            "price_from": 1500000,
            "place_id": "ChIJTest123456",
            "service_type": "residencias"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/residencias/create",
            json=payload,
            headers=self.headers
        )
        
        # Check status code
        assert response.status_code == 200, f"Create residencia failed: {response.text}"
        
        # Check response data
        data = response.json()
        print(f"Created residencia response: {data}")
        
        # Validate returned fields
        assert "provider_id" in data, "Response missing provider_id"
        assert "user_id" in data, "Response missing user_id"
        assert data["business_name"] == payload["business_name"], "Business name mismatch"
        assert data["email"] == test_email, "Email mismatch"
        assert "password" in data, "Response missing auto-generated password"
        assert data["status"] == "created", "Status should be 'created'"
        
        print(f"✓ Created residencia with provider_id: {data['provider_id']}")
        print(f"✓ Auto-generated password: {data['password']}")
        
        # Verify the provider was actually created in DB by fetching it
        provider_response = requests.get(
            f"{BASE_URL}/api/providers/{data['provider_id']}"
        )
        assert provider_response.status_code == 200, f"Failed to fetch created provider: {provider_response.text}"
        
        provider_data = provider_response.json()
        print(f"Fetched provider data: {provider_data}")
        
        # Verify all fields were stored correctly
        assert provider_data["business_name"] == payload["business_name"]
        assert provider_data["phone"] == payload["phone"]
        assert provider_data["address"] == payload["address"]
        assert provider_data["region"] == payload["region"]
        assert provider_data["comuna"] == payload["comuna"]
        assert provider_data.get("place_id") == payload["place_id"]
        
        # Check social links
        social_links = provider_data.get("social_links", {})
        assert social_links.get("website") == payload["website"], f"Website mismatch: {social_links.get('website')}"
        assert social_links.get("facebook") == payload["facebook"], f"Facebook mismatch: {social_links.get('facebook')}"
        assert social_links.get("instagram") == payload["instagram"], f"Instagram mismatch: {social_links.get('instagram')}"
        
        # Check services array contains service_type and price_from
        services = provider_data.get("services", [])
        assert len(services) > 0, "Provider should have at least one service"
        first_service = services[0]
        assert first_service.get("service_type") == payload["service_type"], f"Service type mismatch: {first_service.get('service_type')}"
        assert first_service.get("price_from") == payload["price_from"], f"Price mismatch: {first_service.get('price_from')}"
        
        print("✓ All fields stored correctly in database")
        
    def test_create_residencia_cuidado_domicilio(self):
        """Test creating a residence with service_type = cuidado-domicilio"""
        unique_id = uuid.uuid4().hex[:8]
        
        payload = {
            "business_name": f"Cuidado Domicilio Test {unique_id}",
            "email": f"test_cuidado_{unique_id}@testsenior.cl",
            "phone": "+56987654321",
            "service_type": "cuidado-domicilio",
            "price_from": 750000
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/residencias/create",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Create cuidado domicilio failed: {response.text}"
        data = response.json()
        
        # Verify provider created
        provider_response = requests.get(f"{BASE_URL}/api/providers/{data['provider_id']}")
        provider_data = provider_response.json()
        
        services = provider_data.get("services", [])
        assert len(services) > 0
        assert services[0].get("service_type") == "cuidado-domicilio"
        print("✓ Cuidado domicilio service type created correctly")
        
    def test_create_residencia_salud_mental(self):
        """Test creating a residence with service_type = salud-mental"""
        unique_id = uuid.uuid4().hex[:8]
        
        payload = {
            "business_name": f"Salud Mental Test {unique_id}",
            "email": f"test_salud_{unique_id}@testsenior.cl",
            "service_type": "salud-mental",
            "price_from": 900000
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/residencias/create",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Create salud mental failed: {response.text}"
        data = response.json()
        
        # Verify provider created
        provider_response = requests.get(f"{BASE_URL}/api/providers/{data['provider_id']}")
        provider_data = provider_response.json()
        
        services = provider_data.get("services", [])
        assert len(services) > 0
        assert services[0].get("service_type") == "salud-mental"
        print("✓ Salud mental service type created correctly")


class TestProviderProfileUpdate:
    """Test PUT /api/providers/my-profile with new fields"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as provider to get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "proveedor1@senioradvisor.cl",
            "password": "demo123"
        })
        assert response.status_code == 200, f"Provider login failed: {response.text}"
        self.provider_token = response.json().get("token")
        self.headers = {"Authorization": f"Bearer {self.provider_token}"}
    
    def test_update_profile_with_new_fields(self):
        """Test updating profile with region, place_id, price_from"""
        
        # First get current profile
        get_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=self.headers
        )
        assert get_response.status_code == 200
        current_profile = get_response.json()
        print(f"Current profile: business_name={current_profile.get('business_name')}, region={current_profile.get('region')}")
        
        # Update with new fields
        update_payload = {
            "business_name": current_profile.get("business_name", "Test Provider"),
            "phone": "+56911112222",
            "address": "Av. Updated 456",
            "region": "Región de Valparaíso",
            "comuna": "Viña del Mar",
            "place_id": "ChIJUpdated789",
            "price_from": 2000000
        }
        
        put_response = requests.put(
            f"{BASE_URL}/api/providers/my-profile",
            json=update_payload,
            headers=self.headers
        )
        
        assert put_response.status_code == 200, f"Profile update failed: {put_response.text}"
        print(f"Update response: {put_response.json()}")
        
        # Verify the update persisted
        verify_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=self.headers
        )
        assert verify_response.status_code == 200
        updated_profile = verify_response.json()
        
        # Check all fields were updated
        assert updated_profile["address"] == update_payload["address"], f"Address not updated: {updated_profile['address']}"
        assert updated_profile["region"] == update_payload["region"], f"Region not updated: {updated_profile['region']}"
        assert updated_profile["comuna"] == update_payload["comuna"], f"Comuna not updated: {updated_profile['comuna']}"
        assert updated_profile.get("place_id") == update_payload["place_id"], f"Place ID not updated: {updated_profile.get('place_id')}"
        
        print("✓ All profile fields updated correctly")
        print(f"  - Region: {updated_profile['region']}")
        print(f"  - Comuna: {updated_profile['comuna']}")
        print(f"  - Place ID: {updated_profile.get('place_id')}")
        
    def test_update_social_links(self):
        """Test updating social links via profile update"""
        
        update_payload = {
            "social_links": {
                "website": "https://www.test-provider-website.cl",
                "facebook": "https://facebook.com/testprovider",
                "instagram": "https://instagram.com/testprovider"
            }
        }
        
        put_response = requests.put(
            f"{BASE_URL}/api/providers/my-profile",
            json=update_payload,
            headers=self.headers
        )
        
        assert put_response.status_code == 200, f"Social links update failed: {put_response.text}"
        
        # Verify
        verify_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=self.headers
        )
        updated_profile = verify_response.json()
        social_links = updated_profile.get("social_links", {})
        
        assert social_links.get("website") == update_payload["social_links"]["website"]
        assert social_links.get("facebook") == update_payload["social_links"]["facebook"]
        assert social_links.get("instagram") == update_payload["social_links"]["instagram"]
        
        print("✓ Social links updated correctly")


class TestSearchWithServiceTypes:
    """Test /api/providers search with service type filters"""
    
    def test_search_all_providers(self):
        """Test fetching all providers (Todos)"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        assert len(providers) > 0, "Should return providers"
        print(f"✓ Todos: Found {len(providers)} providers")
        
    def test_search_residencias(self):
        """Test filtering by residencias service type"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=residencias")
        assert response.status_code == 200
        providers = response.json()
        print(f"✓ Residencias filter: Found {len(providers)} providers")
        
        # Verify at least some providers have correct service type
        if providers:
            for p in providers[:5]:  # Check first 5
                services = p.get("services", [])
                if services:
                    service_types = [s.get("service_type") for s in services]
                    # At least one should be residencias
                    assert "residencias" in service_types or len(services) == 0, f"Provider {p.get('business_name')} doesn't have residencias service"
        
    def test_search_cuidado_domicilio(self):
        """Test filtering by cuidado-domicilio service type"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=cuidado-domicilio")
        assert response.status_code == 200
        providers = response.json()
        print(f"✓ Cuidado Domicilio filter: Found {len(providers)} providers")
        
    def test_search_salud_mental(self):
        """Test filtering by salud-mental service type"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=salud-mental")
        assert response.status_code == 200
        providers = response.json()
        print(f"✓ Salud Mental filter: Found {len(providers)} providers")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
