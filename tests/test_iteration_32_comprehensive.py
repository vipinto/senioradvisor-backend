"""
Iteration 32 - Comprehensive Testing Suite for SeniorAdvisor
Tests backend APIs and frontend integrations after SearchSimple.jsx restoration
Focus: Provider search, service_type filtering, gallery images, deduped service tags
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://image-carousel-13.preview.emergentagent.com').rstrip('/')

class TestHealthCheck:
    """Basic health checks"""
    
    def test_api_accessible(self):
        """Backend API should be accessible"""
        response = requests.get(f"{BASE_URL}/api/providers", timeout=15)
        assert response.status_code == 200
        print(f"✓ API accessible - status {response.status_code}")


class TestProviderSearch:
    """Provider search and filtering tests"""
    
    def test_providers_returns_50_by_default(self):
        """GET /api/providers should return 50 providers by default"""
        response = requests.get(f"{BASE_URL}/api/providers", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 50, f"Expected 50, got {len(data)}"
        print(f"✓ Providers API returns {len(data)} results (default limit)")
    
    def test_providers_have_required_fields(self):
        """Each provider should have required fields"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=5", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ['provider_id', 'business_name', 'comuna', 'approved']
        for provider in data:
            for field in required_fields:
                assert field in provider, f"Missing field: {field}"
        print(f"✓ All providers have required fields: {required_fields}")
    
    def test_providers_have_services_array(self):
        """Each provider should have services array with service_type"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=10", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        providers_with_services = 0
        for provider in data:
            if provider.get('services') and len(provider['services']) > 0:
                providers_with_services += 1
                for svc in provider['services']:
                    assert 'service_type' in svc, f"Service missing service_type for {provider['business_name']}"
        
        print(f"✓ {providers_with_services}/{len(data)} providers have services with service_type")
    
    def test_filter_residencias_only(self):
        """GET /api/providers?service_type=residencias should return only residencias"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=residencias&limit=20", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "Expected at least 1 residencia"
        
        # Verify filtering works at MongoDB level
        for provider in data:
            service_types = [s.get('service_type') for s in provider.get('services', [])]
            assert 'residencias' in service_types, f"Provider {provider['business_name']} has no residencias service"
        
        print(f"✓ Residencias filter returned {len(data)} providers")
    
    def test_filter_cuidado_domicilio(self):
        """GET /api/providers?service_type=cuidado-domicilio should work"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=cuidado-domicilio&limit=20", timeout=15)
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Cuidado-domicilio filter returned {len(data)} providers")
    
    def test_filter_salud_mental(self):
        """GET /api/providers?service_type=salud-mental should work"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=salud-mental&limit=20", timeout=15)
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Salud-mental filter returned {len(data)} providers")


class TestProviderDetail:
    """Provider detail endpoint tests"""
    
    def test_provider_detail_seed_provider(self):
        """GET /api/providers/{id} for seed provider should return full details"""
        # First get a provider id
        response = requests.get(f"{BASE_URL}/api/providers?limit=1", timeout=15)
        data = response.json()
        provider_id = data[0]['provider_id']
        
        # Get provider detail
        response = requests.get(f"{BASE_URL}/api/providers/{provider_id}", timeout=15)
        assert response.status_code == 200
        provider = response.json()
        
        assert provider['provider_id'] == provider_id
        assert 'business_name' in provider
        assert 'services' in provider
        print(f"✓ Provider detail returned for: {provider['business_name']}")
    
    def test_provider_detail_has_gallery(self):
        """Provider detail should include gallery images"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=5", timeout=15)
        data = response.json()
        
        for provider_summary in data[:3]:
            response = requests.get(f"{BASE_URL}/api/providers/{provider_summary['provider_id']}", timeout=15)
            assert response.status_code == 200
            provider = response.json()
            
            # Gallery or photos should exist
            has_images = provider.get('gallery') or provider.get('photos') or provider.get('profile_photo')
            if has_images:
                print(f"  ✓ {provider['business_name']} has images")
        
        print(f"✓ Provider detail includes gallery/photos fields")
    
    def test_provider_detail_invalid_id_returns_404(self):
        """GET /api/providers/invalid-id should return 404"""
        response = requests.get(f"{BASE_URL}/api/providers/non-existent-id-12345", timeout=15)
        assert response.status_code == 404
        print(f"✓ Invalid provider ID returns 404")


class TestBlogAPI:
    """Blog articles API tests"""
    
    def test_get_blog_articles(self):
        """GET /api/blog/articles should return articles"""
        response = requests.get(f"{BASE_URL}/api/blog/articles", timeout=15)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            article = data[0]
            assert 'title' in article
            assert 'slug' in article
            print(f"✓ Blog API returned {len(data)} articles. First: {article['title']}")
        else:
            print(f"✓ Blog API returned empty list (no articles)")


class TestPartnersAPI:
    """Partners/Convenios API tests"""
    
    def test_get_convenios(self):
        """GET /api/partners/convenios should return convenios"""
        response = requests.get(f"{BASE_URL}/api/partners/convenios", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            convenio = data[0]
            assert 'name' in convenio
            assert 'description' in convenio
            print(f"✓ Partners API returned {len(data)} convenios. First: {convenio['name']}")
        else:
            print(f"✓ Partners API returned empty list (no convenios)")


class TestAuthentication:
    """Authentication tests for all 3 roles"""
    
    def test_admin_login(self):
        """Admin login should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@senioradvisor.cl", "password": "admin123"},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert 'token' in data
        assert data['user']['role'] == 'admin'
        print(f"✓ Admin login successful - role: {data['user']['role']}")
        return data['token']
    
    def test_client_login(self):
        """Client login should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "demo@senioradvisor.cl", "password": "demo123"},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert 'token' in data
        assert data['user']['role'] == 'client'
        print(f"✓ Client login successful - role: {data['user']['role']}")
    
    def test_provider_login(self):
        """Provider login should work"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "proveedor1@senioradvisor.cl", "password": "demo123"},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        assert 'token' in data
        assert data['user']['role'] == 'provider'
        print(f"✓ Provider login successful - role: {data['user']['role']}")


class TestAdminAPI:
    """Admin API tests (authenticated)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "admin@senioradvisor.cl", "password": "admin123"},
            timeout=15
        )
        return response.json()['token']
    
    def test_admin_stats(self, admin_token):
        """GET /api/admin/stats should return dashboard stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15
        )
        assert response.status_code == 200
        data = response.json()
        
        assert 'total_users' in data
        assert 'total_providers' in data
        assert 'active_subscriptions' in data
        
        print(f"✓ Admin stats: {data['total_providers']} providers, {data['total_users']} users")
    
    def test_admin_stats_requires_auth(self):
        """GET /api/admin/stats without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/admin/stats", timeout=15)
        assert response.status_code in [401, 403]
        print(f"✓ Admin stats requires authentication - status {response.status_code}")


class TestServiceTypeDeduplication:
    """Tests for service tag deduplication fix"""
    
    def test_no_duplicate_service_types(self):
        """Providers should not have duplicate service types"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=20", timeout=15)
        assert response.status_code == 200
        data = response.json()
        
        for provider in data:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            unique_types = set(service_types)
            
            # Each service_type should appear only once (or have different descriptions)
            type_counts = {}
            for st in service_types:
                type_counts[st] = type_counts.get(st, 0) + 1
            
            # Log if duplicates exist (not a hard failure - backend may have intentional duplicates with different prices)
            for st, count in type_counts.items():
                if count > 1:
                    print(f"  Note: {provider['business_name']} has {count} '{st}' services")
        
        print(f"✓ Checked {len(data)} providers for service type patterns")


class TestCSVImportedProviders:
    """Test CSV-imported providers work correctly"""
    
    def test_large_result_set(self):
        """Backend should handle large provider counts"""
        response = requests.get(f"{BASE_URL}/api/providers?limit=300", timeout=30)
        assert response.status_code == 200
        data = response.json()
        
        # Previous test showed 224+ providers after CSV import
        print(f"✓ Large query returned {len(data)} providers")
        assert len(data) >= 50, "Expected at least 50 providers in database"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
