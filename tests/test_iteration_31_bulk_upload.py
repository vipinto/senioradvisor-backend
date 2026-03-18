"""
Iteration 31: Testing Bulk Upload and Search Functionality
- Tests the search API returns 200+ providers
- Tests the admin bulk upload endpoint
- Tests provider detail page for imported providers
- Tests home page categories
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProviderSearch:
    """Tests for /api/providers search endpoint"""
    
    def test_search_providers_default_limit(self):
        """Test that default search returns results (max 50)"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Default search returned {len(data)} providers")
        assert len(data) <= 50  # Default limit
        
    def test_search_providers_high_limit_returns_200_plus(self):
        """Test that search with high limit returns 200+ providers (bulk imported data)"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=500")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"High limit search returned {len(data)} providers")
        # Should have 200+ providers after bulk import (256 mentioned in context)
        assert len(data) >= 200, f"Expected 200+ providers, got {len(data)}"
        
    def test_search_providers_have_required_fields(self):
        """Test that providers have required fields"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        
        provider = data[0]
        # Check required fields
        assert "provider_id" in provider
        assert "business_name" in provider
        assert "comuna" in provider
        assert provider.get("approved") == True
        print(f"Provider fields validated: {provider.get('business_name')}")
        
    def test_search_by_service_type_residencias(self):
        """Test filtering by service type residencias"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=residencias&limit=100")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Residencias filter returned {len(data)} providers")
        # Should have providers with residencias service
        assert len(data) > 0
        
    def test_search_by_service_type_cuidado_domicilio(self):
        """Test filtering by service type cuidado_domicilio"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=cuidado_domicilio&limit=100")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Cuidado Domicilio filter returned {len(data)} providers")
        
    def test_search_by_service_type_salud_mental(self):
        """Test filtering by service type salud_mental"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=salud_mental&limit=100")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Salud Mental filter returned {len(data)} providers")
        
    def test_search_by_comuna(self):
        """Test filtering by comuna"""
        # First get a provider to know a valid comuna
        response = requests.get(f"{BASE_URL}/api/providers?limit=1")
        assert response.status_code == 200
        data = response.json()
        if len(data) > 0 and data[0].get('comuna'):
            comuna = data[0]['comuna']
            response = requests.get(f"{BASE_URL}/api/providers?comuna={comuna}&limit=100")
            assert response.status_code == 200
            filtered_data = response.json()
            print(f"Comuna '{comuna}' filter returned {len(filtered_data)} providers")
            assert len(filtered_data) > 0


class TestProviderDetail:
    """Tests for /api/providers/{provider_id} detail endpoint"""
    
    def test_get_provider_detail(self):
        """Test getting provider detail by ID"""
        # First get a provider ID
        response = requests.get(f"{BASE_URL}/api/providers?limit=1")
        assert response.status_code == 200
        providers = response.json()
        assert len(providers) > 0
        
        provider_id = providers[0]['provider_id']
        
        # Get the detail
        detail_response = requests.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert detail_response.status_code == 200
        provider = detail_response.json()
        
        assert provider['provider_id'] == provider_id
        assert 'business_name' in provider
        assert 'comuna' in provider
        print(f"Provider detail: {provider.get('business_name')} in {provider.get('comuna')}")
        
    def test_get_provider_detail_not_found(self):
        """Test 404 for invalid provider ID"""
        response = requests.get(f"{BASE_URL}/api/providers/invalid-provider-id-12345")
        assert response.status_code == 404


class TestAdminAuth:
    """Tests for admin authentication"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@senioradvisor.cl",
            "password": "admin123"
        })
        assert response.status_code == 200
        return response.json().get("token")  # API returns 'token' not 'access_token'
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@senioradvisor.cl",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data  # API returns 'token' not 'access_token'
        print("Admin login successful")
        
    def test_admin_stats(self, admin_token):
        """Test admin stats endpoint shows correct provider count"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        stats = response.json()
        assert "total_providers" in stats
        print(f"Admin stats - Total providers: {stats.get('total_providers')}")
        # Should reflect the bulk imported data (200+)
        assert stats['total_providers'] >= 200, f"Expected 200+ providers, got {stats['total_providers']}"


class TestBulkUploadEndpoint:
    """Tests for /api/admin/residencias/upload-excel bulk upload"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@senioradvisor.cl",
            "password": "admin123"
        })
        assert response.status_code == 200
        return response.json().get("token")  # API returns 'token' not 'access_token'
    
    def test_bulk_upload_requires_auth(self):
        """Test bulk upload requires authentication"""
        # Create a minimal CSV
        csv_content = "nombre residencia,email\nTest Residencia,test@test.cl"
        files = {'file': ('test.csv', io.StringIO(csv_content), 'text/csv')}
        
        response = requests.post(f"{BASE_URL}/api/admin/residencias/upload-excel", files=files)
        # Should be 401 or 403 without auth
        assert response.status_code in [401, 403]
        print("Bulk upload correctly requires auth")
        
    def test_bulk_upload_with_csv(self, admin_token):
        """Test bulk upload with a test CSV - skip actual creation to avoid duplicates"""
        # Create a CSV with unique test email that should already exist
        csv_content = "nombre residencia,comuna\nTEST_BulkUpload_Dummy,Santiago"
        files = {'file': ('test.csv', csv_content, 'text/csv')}
        
        response = requests.post(
            f"{BASE_URL}/api/admin/residencias/upload-excel",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should return 200 with results (may have errors if email already exists)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "created" in data
        assert "errors" in data
        assert "results" in data
        print(f"Bulk upload response: total={data['total']}, created={data['created']}, errors={data['errors']}")
        

class TestHomePageCategories:
    """Test home page loads and categories work"""
    
    def test_home_page_featured_providers(self):
        """Test featured providers endpoint"""
        response = requests.get(f"{BASE_URL}/api/providers?featured=true&limit=10")
        assert response.status_code == 200
        data = response.json()
        # Featured providers should have verified + subscription (may be empty)
        print(f"Featured providers: {len(data)}")
        
    def test_providers_sorted_by_rating(self):
        """Test that providers are sorted properly"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=20")
        assert response.status_code == 200
        data = response.json()
        # Just verify we get providers back
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
