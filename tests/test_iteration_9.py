"""
Test Suite for Iteration 9 Features:
- Provider info gating (non-subscribed vs subscribed users)
- Reviews with photo upload (max 4 photos, only subscribed users)
- 'Cuidador' terminology (no 'Negocio/Proveedor' in UI)
- Admin metrics time-series data
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://image-carousel-13.preview.emergentagent.com').rstrip('/')


class TestProviderInfoGating:
    """Test provider information masking based on subscription status"""

    def test_providers_list_non_authenticated_shows_masked_data(self):
        """Non-authenticated users see first name only, no phone/address"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        
        providers = response.json()
        assert len(providers) > 0, "Should have at least one provider"
        
        for provider in providers:
            # Should be masked
            assert provider.get('full_name_hidden') == True, f"full_name_hidden should be True, got {provider.get('full_name_hidden')}"
            assert provider.get('phone') is None, f"phone should be None, got {provider.get('phone')}"
            assert provider.get('address') is None, f"address should be None, got {provider.get('address')}"
            # Business name should be first word only
            business_name = provider.get('business_name', '')
            assert ' ' not in business_name, f"business_name should be first word only, got '{business_name}'"

    def test_provider_detail_non_authenticated_contact_blocked(self):
        """Non-authenticated users see contact_blocked=True on provider detail"""
        # Get a provider ID first
        list_response = requests.get(f"{BASE_URL}/api/providers")
        assert list_response.status_code == 200
        providers = list_response.json()
        assert len(providers) > 0
        
        provider_id = providers[0]['provider_id']
        
        response = requests.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert response.status_code == 200
        
        provider = response.json()
        assert provider.get('contact_blocked') == True, f"contact_blocked should be True"
        assert provider.get('full_name_hidden') == True, f"full_name_hidden should be True"
        assert provider.get('phone') is None, f"phone should be None"
        assert provider.get('address') is None, f"address should be None"
        assert provider.get('whatsapp') is None, f"whatsapp should be None"

    def test_provider_detail_authenticated_no_subscription_still_blocked(self):
        """Authenticated user without subscription still sees blocked contact"""
        # Login as admin (no subscription by default)
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        token = login_response.json().get('token')
        
        # Get provider list for provider_id
        list_response = requests.get(f"{BASE_URL}/api/providers")
        providers = list_response.json()
        provider_id = providers[0]['provider_id']
        
        # Get provider detail with token
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/providers/{provider_id}", headers=headers)
        assert response.status_code == 200
        
        provider = response.json()
        # Admin without subscription should still see blocked
        assert provider.get('contact_blocked') == True


class TestReviewPhotoUpload:
    """Test review photo upload functionality"""

    def test_photo_upload_requires_authentication(self):
        """Photo upload should require authentication"""
        # Create a fake image
        files = {'file': ('test.jpg', b'fake image data', 'image/jpeg')}
        response = requests.post(f"{BASE_URL}/api/reviews/upload-photo", files=files)
        assert response.status_code == 401 or response.json().get('detail') == 'No autenticado'

    def test_photo_upload_requires_subscription(self):
        """Photo upload requires active subscription"""
        # Login as admin (no subscription)
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        token = login_response.json().get('token')
        
        # Try to upload photo
        headers = {"Authorization": f"Bearer {token}"}
        files = {'file': ('test.jpg', b'fake image data', 'image/jpeg')}
        response = requests.post(f"{BASE_URL}/api/reviews/upload-photo", files=files, headers=headers)
        
        # Should fail because no subscription
        assert response.status_code in [401, 403] or 'suscripci' in response.json().get('detail', '').lower()

    def test_review_create_requires_subscription(self):
        """Creating a review requires active subscription"""
        # Login as admin (no subscription)
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        token = login_response.json().get('token')
        
        # Get a provider ID
        list_response = requests.get(f"{BASE_URL}/api/providers")
        providers = list_response.json()
        provider_id = providers[0]['provider_id']
        
        # Try to create review
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        response = requests.post(f"{BASE_URL}/api/reviews", json={
            "provider_id": provider_id,
            "rating": 5,
            "comment": "Test review",
            "photos": []
        }, headers=headers)
        
        # Should fail because no subscription
        assert response.status_code in [401, 403] or 'suscripci' in response.json().get('detail', '').lower()


class TestAdminMetrics:
    """Test admin metrics endpoint"""

    def test_admin_metrics_requires_authentication(self):
        """Admin metrics should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/metrics")
        assert response.status_code == 401 or response.json().get('detail') == 'No autenticado'

    def test_admin_metrics_returns_6_months_data(self):
        """Admin metrics returns 6 months of time-series data"""
        # Login as admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        token = login_response.json().get('token')
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/admin/metrics", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Should return a list"
        assert len(data) == 6, f"Should return 6 months of data, got {len(data)}"
        
        # Each entry should have required fields
        for entry in data:
            assert 'month' in entry, "Entry should have 'month'"
            assert 'users' in entry, "Entry should have 'users'"
            assert 'providers' in entry, "Entry should have 'providers'"
            assert 'subscriptions' in entry, "Entry should have 'subscriptions'"
            assert 'reviews' in entry, "Entry should have 'reviews'"


class TestReviewModelPhotos:
    """Test that ReviewCreate model accepts photos field"""

    def test_review_model_accepts_photos_array(self):
        """Verify ReviewCreate model accepts photos field in the request"""
        # Login as admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        token = login_response.json().get('token')
        
        # Get a provider ID
        list_response = requests.get(f"{BASE_URL}/api/providers")
        providers = list_response.json()
        provider_id = providers[0]['provider_id']
        
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # Try to create review with photos field - should fail due to subscription
        # but the error should NOT be about invalid field
        response = requests.post(f"{BASE_URL}/api/reviews", json={
            "provider_id": provider_id,
            "rating": 5,
            "comment": "Test review with photos",
            "photos": ["/uploads/reviews/test1.jpg", "/uploads/reviews/test2.jpg"]
        }, headers=headers)
        
        # The error should be about subscription, not about invalid 'photos' field
        if response.status_code != 200:
            error_detail = response.json().get('detail', '')
            assert 'photos' not in error_detail.lower(), f"Model should accept 'photos' field, got error: {error_detail}"


class TestProviderServices:
    """Test provider services have pet_sizes"""

    def test_providers_services_have_pet_sizes(self):
        """Provider services should include pet_sizes field"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        
        providers = response.json()
        found_pet_sizes = False
        
        for provider in providers:
            services = provider.get('services', [])
            for service in services:
                if 'pet_sizes' in service:
                    found_pet_sizes = True
                    assert isinstance(service['pet_sizes'], list)
                    for size in service['pet_sizes']:
                        assert size in ['pequeno', 'mediano', 'grande'], f"Invalid pet size: {size}"
        
        assert found_pet_sizes, "At least one service should have pet_sizes"


class TestServiceTypes:
    """Test service type filtering"""

    def test_service_type_alojamiento(self):
        """Test filtering by alojamiento service type"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=alojamiento")
        assert response.status_code == 200
        
        providers = response.json()
        for provider in providers:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            assert 'alojamiento' in service_types, f"Filtered provider should have alojamiento service"

    def test_service_type_guarderia(self):
        """Test filtering by guarderia service type"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=guarderia")
        assert response.status_code == 200
        
        providers = response.json()
        for provider in providers:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            assert 'guarderia' in service_types, f"Filtered provider should have guarderia service"

    def test_service_type_paseo(self):
        """Test filtering by paseo service type"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=paseo")
        assert response.status_code == 200
        
        providers = response.json()
        for provider in providers:
            services = provider.get('services', [])
            service_types = [s.get('service_type') for s in services]
            assert 'paseo' in service_types, f"Filtered provider should have paseo service"


class TestHealthAndBasics:
    """Basic API tests"""

    def test_health_endpoint(self):
        """Health check endpoint works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json().get('status') == 'healthy'

    def test_subscription_plans_endpoint(self):
        """Subscription plans endpoint works"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        plans = response.json()
        assert isinstance(plans, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
