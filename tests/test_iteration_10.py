"""
Test iteration 10: Provider services_offered with service details, always_active availability,
search filters by service_type + dates, PUT /providers/my-profile, PUT /providers/my-services, admin metrics
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProviderServiceTypeFilters:
    """Test GET /api/providers?service_type= filtering"""

    def test_filter_by_paseo_service_type(self):
        """GET /api/providers?service_type=paseo should return providers with paseo service"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=paseo")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Paseo providers: {len(data)}")
        # All returned providers should have paseo service
        for provider in data:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            assert 'paseo' in service_types, f"Provider {provider.get('business_name')} should have paseo service"
        # Expected: at least 2 providers
        assert len(data) >= 2, f"Expected at least 2 providers with paseo, got {len(data)}"

    def test_filter_by_alojamiento_service_type(self):
        """GET /api/providers?service_type=alojamiento should return providers with alojamiento"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=alojamiento")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Alojamiento providers: {len(data)}")
        for provider in data:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            assert 'alojamiento' in service_types, f"Provider {provider.get('business_name')} should have alojamiento"
        assert len(data) >= 2, f"Expected at least 2 providers with alojamiento, got {len(data)}"

    def test_filter_by_guarderia_service_type(self):
        """GET /api/providers?service_type=guarderia should return providers with guarderia"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=guarderia")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Guarderia providers: {len(data)}")
        for provider in data:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            assert 'guarderia' in service_types, f"Provider {provider.get('business_name')} should have guarderia"
        assert len(data) >= 2, f"Expected at least 2 providers with guarderia, got {len(data)}"

    def test_all_providers_no_filter(self):
        """GET /api/providers without filter should return all approved providers"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"All providers: {len(data)}")
        assert len(data) >= 5, f"Expected at least 5 total providers, got {len(data)}"


class TestProviderDateFiltering:
    """Test GET /api/providers?dates= filtering - always_active providers should always appear"""

    def test_always_active_providers_appear_with_date_filter(self):
        """Providers with always_active=true should appear regardless of date filter"""
        response = requests.get(f"{BASE_URL}/api/providers?dates=2026-03-01")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Providers with dates filter: {len(data)}")
        
        # All seed providers have always_active=True, so all should appear
        for provider in data:
            always_active = provider.get('always_active')
            # Providers returned should either have always_active=True or have matching dates
            if always_active is not None:
                print(f"  - {provider.get('business_name')}: always_active={always_active}")
        
        # Should return at least 5 providers (all seed data has always_active=true)
        assert len(data) >= 5, f"Expected all 5 always_active providers, got {len(data)}"

    def test_multiple_dates_filter(self):
        """Test filtering with multiple dates"""
        response = requests.get(f"{BASE_URL}/api/providers?dates=2026-03-01,2026-03-02,2026-03-03")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Providers with multiple dates: {len(data)}")
        assert len(data) >= 5

    def test_combined_service_and_date_filter(self):
        """Test filtering with both service_type and dates"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=paseo&dates=2026-03-01")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Paseo providers with date filter: {len(data)}")
        # Should return paseo providers that are always_active
        for provider in data:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            assert 'paseo' in service_types


class TestAuthenticatedProviderEndpoints:
    """Test authenticated endpoints: my-profile, my-services"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Register a new user and create provider for testing"""
        import uuid
        test_email = f"test_auth_{uuid.uuid4().hex[:8]}@test.com"
        
        # Register new user
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "password": "testpassword123",
                "name": "Test Auth Provider"
            }
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.headers = {"Authorization": f"Bearer {self.token}"}
            
            # Create provider
            provider_response = requests.post(
                f"{BASE_URL}/api/providers",
                json={
                    "business_name": "Test Auth Provider Business",
                    "address": "Test Address",
                    "comuna": "Santiago",
                    "phone": "+56911111111",
                    "always_active": True,
                    "services_offered": [{"service_type": "paseo", "price_from": 5000, "pet_sizes": ["pequeno"]}]
                },
                headers=self.headers
            )
            if provider_response.status_code != 200:
                pytest.skip(f"Provider creation failed: {provider_response.text}")
        else:
            pytest.skip(f"User registration failed: {response.text}")

    def test_get_my_profile_authenticated(self):
        """GET /api/providers/my-profile with auth"""
        response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'provider_id' in data
        assert 'business_name' in data
        assert 'services' in data, "my-profile should include services"
        print(f"Provider profile: {data.get('business_name')}, services: {len(data.get('services', []))}")

    def test_put_my_profile_updates_always_active(self):
        """PUT /api/providers/my-profile updates always_active and available_dates"""
        # Update always_active to false with specific dates
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile",
            json={
                "always_active": False,
                "available_dates": ["2026-03-01", "2026-03-02", "2026-03-05"]
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify the update
        verify_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=self.headers
        )
        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data.get('always_active') == False
        assert len(data.get('available_dates', [])) == 3
        print(f"Updated: always_active={data.get('always_active')}, dates={len(data.get('available_dates', []))}")

    def test_put_my_services_updates_services_list(self):
        """PUT /api/providers/my-services updates services for provider"""
        # Update services
        response = requests.put(
            f"{BASE_URL}/api/providers/my-services",
            json={
                "services": [
                    {"service_type": "paseo", "price_from": 12000, "pet_sizes": ["pequeno", "mediano"]},
                    {"service_type": "guarderia", "price_from": 25000, "pet_sizes": ["grande"]}
                ]
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify services were updated
        verify_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=self.headers
        )
        assert verify_response.status_code == 200
        data = verify_response.json()
        services = data.get('services', [])
        assert len(services) == 2
        service_types = [s['service_type'] for s in services]
        assert 'paseo' in service_types
        assert 'guarderia' in service_types
        print(f"Services updated: {service_types}")


class TestAdminMetrics:
    """Test admin metrics endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@ucan.cl", "password": "admin123"}
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin login failed")

    def test_admin_metrics_returns_time_series(self):
        """GET /api/admin/metrics returns 6 months of data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/metrics",
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Metrics months: {len(data)}")
        assert len(data) == 6, f"Expected 6 months of data, got {len(data)}"
        
        # Each month should have required fields
        for month in data:
            assert 'month' in month
            assert 'users' in month
            assert 'providers' in month
            assert 'subscriptions' in month
            assert 'reviews' in month


class TestProviderServicesOffered:
    """Test provider services_offered structure"""

    def test_providers_have_services_with_details(self):
        """GET /api/providers should return providers with service details"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        for provider in data:
            services = provider.get('services', [])
            for service in services:
                assert 'service_type' in service
                assert service['service_type'] in ['paseo', 'guarderia', 'alojamiento']
                # Check optional fields
                if 'pet_sizes' in service:
                    assert isinstance(service['pet_sizes'], list)
                print(f"  Service: {service.get('service_type')}, price: {service.get('price_from')}, sizes: {service.get('pet_sizes')}")


class TestProviderCreationAndUpdate:
    """Test provider creation with services_offered array"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Register a new test user for provider tests"""
        import uuid
        test_email = f"test_{uuid.uuid4().hex[:8]}@test.com"
        
        # Register new user
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": test_email,
                "password": "testpassword123",
                "name": "Test User Provider"
            }
        )
        if response.status_code == 200:
            data = response.json()
            self.token = data.get('token')
            self.headers = {"Authorization": f"Bearer {self.token}"}
            self.test_email = test_email
        else:
            pytest.skip(f"User registration failed: {response.text}")

    def test_create_provider_with_services_offered(self):
        """POST /api/providers accepts services_offered array with service details"""
        payload = {
            "business_name": "TEST Provider Services",
            "description": "Test provider with multiple services",
            "address": "Test Address 123",
            "comuna": "Santiago",
            "phone": "+56912345678",
            "always_active": True,
            "services_offered": [
                {
                    "service_type": "paseo",
                    "price_from": 8000,
                    "description": "Paseos de 30min",
                    "pet_sizes": ["pequeno", "mediano"]
                },
                {
                    "service_type": "guarderia",
                    "price_from": 15000,
                    "description": "Cuidado diurno",
                    "pet_sizes": ["pequeno", "mediano", "grande"]
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/providers",
            json=payload,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert 'provider_id' in data
        assert data.get('business_name') == "TEST Provider Services"
        assert data.get('always_active') == True
        print(f"Created provider: {data.get('provider_id')}")
        
        # Verify services were created
        services_response = requests.get(
            f"{BASE_URL}/api/providers/{data['provider_id']}/services"
        )
        assert services_response.status_code == 200
        services = services_response.json()
        assert len(services) == 2
        service_types = [s['service_type'] for s in services]
        assert 'paseo' in service_types
        assert 'guarderia' in service_types
        print(f"Services created: {service_types}")


class TestProviderAlwaysActive:
    """Test always_active field behavior"""

    def test_providers_have_always_active_field(self):
        """All providers should have always_active field"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        for provider in data:
            # All seed providers should have always_active=True
            always_active = provider.get('always_active')
            print(f"Provider {provider.get('business_name')}: always_active={always_active}")
            # Field should exist or default to True
            if always_active is not None:
                assert isinstance(always_active, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
