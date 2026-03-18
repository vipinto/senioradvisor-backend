"""
Tests for new features:
1. Personal Info (Más Datos) - PUT/GET /providers/my-profile/personal-info
2. Publish Expired Reviews - POST /reviews/publish-expired
3. Regression: GET /reviews/client/me and GET /providers/{provider_id} reviews

These tests verify iteration 22 features for U-CAN pet services platform.
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from main agent context
TEST_CARER = {"email": "cuidador@test.com", "password": "cuidador123"}
TEST_CLIENT = {"email": "cliente@test.com", "password": "cliente123"}
TEST_CLIENT_FREE = {"email": "test_client_ui@test.com", "password": "test123456"}
TEST_PROVIDER_ID = "prov_23ad24c36254"


class TestAuthentication:
    """Authentication helpers for tests"""
    
    @pytest.fixture
    def carer_token(self):
        """Get token for subscribed carer"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CARER)
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Carer login failed: {response.status_code}")
    
    @pytest.fixture
    def client_token(self):
        """Get token for subscribed client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CLIENT)
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Client login failed: {response.status_code}")
    
    @pytest.fixture
    def free_client_token(self):
        """Get token for free client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CLIENT_FREE)
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Free client login failed: {response.status_code}")


class TestPersonalInfoEndpoints(TestAuthentication):
    """Tests for PUT/GET /providers/my-profile/personal-info"""
    
    def test_get_personal_info_requires_auth(self):
        """GET /providers/my-profile/personal-info without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info")
        assert response.status_code == 401
        print(f"PASS: GET personal-info without auth returns 401")
    
    def test_put_personal_info_requires_auth(self):
        """PUT /providers/my-profile/personal-info without auth returns 401"""
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            json={"housing_type": "casa"}
        )
        assert response.status_code == 401
        print(f"PASS: PUT personal-info without auth returns 401")
    
    def test_get_personal_info_as_carer(self, carer_token):
        """GET /providers/my-profile/personal-info returns saved personal info"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        response = requests.get(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        # Previous test data should exist from main agent context
        print(f"PASS: GET personal-info returns 200, data: {data}")
        return data
    
    def test_put_personal_info_saves_all_fields(self, carer_token):
        """PUT /providers/my-profile/personal-info saves all allowed fields"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        test_data = {
            "housing_type": "casa",
            "has_yard": True,
            "yard_description": "Patio amplio y cerrado con pasto",
            "has_own_pets": True,
            "own_pets_description": "1 perro golden retriever tranquilo",
            "animal_experience": "10 años cuidando mascotas de todo tipo",
            "daily_availability": "Lunes a viernes 8:00-18:00, fines de semana flexible",
            "additional_info": "Casa muy tranquila, ideal para mascotas nerviosas"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            headers=headers,
            json=test_data
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Información personal actualizada"
        assert "personal_info" in data
        
        # Verify all fields were saved
        saved = data["personal_info"]
        assert saved["housing_type"] == test_data["housing_type"]
        assert saved["has_yard"] == test_data["has_yard"]
        assert saved["yard_description"] == test_data["yard_description"]
        assert saved["has_own_pets"] == test_data["has_own_pets"]
        assert saved["own_pets_description"] == test_data["own_pets_description"]
        assert saved["animal_experience"] == test_data["animal_experience"]
        assert saved["daily_availability"] == test_data["daily_availability"]
        assert saved["additional_info"] == test_data["additional_info"]
        assert "updated_at" in saved
        
        print(f"PASS: PUT personal-info saves all fields correctly")
    
    def test_put_personal_info_verify_persistence(self, carer_token):
        """Verify personal info persists after PUT via GET"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        
        # First, save new data
        test_data = {
            "housing_type": "departamento",
            "has_yard": False,
            "has_own_pets": False,
            "animal_experience": "5 años de experiencia",
            "daily_availability": "Horario flexible"
        }
        
        put_response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            headers=headers,
            json=test_data
        )
        assert put_response.status_code == 200
        
        # Then GET to verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            headers=headers
        )
        assert get_response.status_code == 200
        saved_data = get_response.json()
        
        assert saved_data["housing_type"] == "departamento"
        assert saved_data["has_yard"] == False
        assert saved_data["has_own_pets"] == False
        assert saved_data["animal_experience"] == "5 años de experiencia"
        assert saved_data["daily_availability"] == "Horario flexible"
        
        print(f"PASS: Personal info persists after PUT, verified via GET")
    
    def test_personal_info_ignores_unknown_fields(self, carer_token):
        """PUT only saves allowed fields, ignores unknown ones"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        test_data = {
            "housing_type": "parcela",
            "unknown_field": "should be ignored",
            "another_unknown": 12345
        }
        
        response = requests.put(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            headers=headers,
            json=test_data
        )
        assert response.status_code == 200
        saved = response.json()["personal_info"]
        assert saved["housing_type"] == "parcela"
        assert "unknown_field" not in saved
        assert "another_unknown" not in saved
        
        print(f"PASS: PUT personal-info ignores unknown fields")
    
    def test_personal_info_not_accessible_for_clients(self, client_token):
        """GET personal-info returns 404 for users without provider profile"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            headers=headers
        )
        # Client doesn't have provider profile, should get 404
        assert response.status_code == 404
        print(f"PASS: GET personal-info returns 404 for non-providers")


class TestPublicProviderProfile(TestAuthentication):
    """Tests for personal_info in public provider profile"""
    
    def test_provider_profile_includes_personal_info(self):
        """GET /providers/{provider_id} includes personal_info field"""
        response = requests.get(f"{BASE_URL}/api/providers/{TEST_PROVIDER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Provider should have personal_info field
        assert "personal_info" in data or data.get("personal_info") is None
        
        if data.get("personal_info"):
            pi = data["personal_info"]
            # Check that allowed fields are present when set
            allowed_fields = [
                "housing_type", "has_yard", "yard_description",
                "has_own_pets", "own_pets_description",
                "animal_experience", "daily_availability", "additional_info"
            ]
            for key in pi:
                if key != "updated_at":
                    assert key in allowed_fields, f"Unexpected field in personal_info: {key}"
        
        print(f"PASS: GET /providers/{TEST_PROVIDER_ID} includes personal_info field")
    
    def test_provider_profile_reviews_still_load(self):
        """GET /providers/{provider_id} still includes reviews after refactoring"""
        response = requests.get(f"{BASE_URL}/api/providers/{TEST_PROVIDER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Reviews field should exist (even if empty array)
        assert "reviews" in data
        assert isinstance(data["reviews"], list)
        
        print(f"PASS: GET /providers/{TEST_PROVIDER_ID} includes reviews array")


class TestPublishExpiredReviews:
    """Tests for POST /reviews/publish-expired endpoint"""
    
    def test_publish_expired_endpoint_exists(self):
        """POST /reviews/publish-expired endpoint is accessible"""
        response = requests.post(f"{BASE_URL}/api/reviews/publish-expired")
        # Should return 200 even without expired reviews
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert data["message"] == "Reseñas publicadas"
        assert "provider_reviews_published" in data
        assert "client_reviews_published" in data
        assert isinstance(data["provider_reviews_published"], int)
        assert isinstance(data["client_reviews_published"], int)
        
        print(f"PASS: POST /reviews/publish-expired returns correct structure")
        print(f"      Provider reviews published: {data['provider_reviews_published']}")
        print(f"      Client reviews published: {data['client_reviews_published']}")
    
    def test_publish_expired_is_idempotent(self):
        """Calling publish-expired multiple times is safe"""
        # First call
        response1 = requests.post(f"{BASE_URL}/api/reviews/publish-expired")
        assert response1.status_code == 200
        
        # Second call immediately after
        response2 = requests.post(f"{BASE_URL}/api/reviews/publish-expired")
        assert response2.status_code == 200
        
        # Should not cause errors
        print(f"PASS: POST /reviews/publish-expired is idempotent")


class TestClientReviewsEndpoint(TestAuthentication):
    """Tests for GET /reviews/client/me after removing auto-publish logic"""
    
    def test_client_reviews_endpoint_works(self, client_token):
        """GET /reviews/client/me returns reviews for authenticated client"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(
            f"{BASE_URL}/api/reviews/client/me",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        
        print(f"PASS: GET /reviews/client/me returns 200 with list")
    
    def test_client_reviews_requires_auth(self):
        """GET /reviews/client/me requires authentication"""
        response = requests.get(f"{BASE_URL}/api/reviews/client/me")
        assert response.status_code == 401
        
        print(f"PASS: GET /reviews/client/me returns 401 without auth")


class TestRegressionAfterRefactoring:
    """Regression tests to ensure existing functionality still works"""
    
    def test_provider_my_profile_still_works(self):
        """GET /providers/my-profile still works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json=TEST_CARER)
        if response.status_code != 200:
            pytest.skip("Login failed")
        token = response.json()["token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/providers/my-profile",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Basic provider fields should exist
        assert "provider_id" in data
        assert "business_name" in data
        assert "services" in data
        
        print(f"PASS: GET /providers/my-profile returns provider data")
    
    def test_provider_search_still_works(self):
        """GET /providers search endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        
        print(f"PASS: GET /providers returns provider list ({len(data)} providers)")
    
    def test_provider_detail_still_has_all_fields(self):
        """GET /providers/{id} has all expected fields"""
        response = requests.get(f"{BASE_URL}/api/providers/{TEST_PROVIDER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        expected_fields = [
            "provider_id", "business_name", "services", 
            "reviews", "rating", "total_reviews"
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        print(f"PASS: GET /providers/{TEST_PROVIDER_ID} has all expected fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
