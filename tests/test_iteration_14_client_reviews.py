"""
Backend tests for iteration 14 - Bidirectional rating system (Client Reviews)
New features:
1. POST /api/reviews/client - Carer reviews a client (requires provider role)
2. GET /api/reviews/client/{user_id} - Get reviews for a specific client
3. GET /api/reviews/client/me - Get reviews about current user as a client
4. GET /api/reviews/provider/given - Get all reviews given by current provider
5. ClientReviewCreate model with sub-ratings (punctuality, pet_behavior, communication)

Regression:
- Login still works
- Dashboard loads (GET /api/auth/me, GET /api/pets, GET /api/favorites)
- Provider dashboard works (GET /api/providers/my-profile)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@ucan.cl"
ADMIN_PASSWORD = "admin123"


class TestHealthAndAuth:
    """Health check and authentication tests"""

    def test_health_check(self):
        """API health endpoint should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")

    def test_admin_login(self):
        """Login as admin user (regression)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✓ Admin login successful, role: {data['user'].get('role')}")


class TestClientReviewsEndpoints:
    """Tests for the new client reviews feature"""

    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["token"]

    @pytest.fixture(scope="class")
    def provider_token_and_data(self):
        """Create a provider user for testing"""
        unique = uuid.uuid4().hex[:6]
        email = f"provider_test_{unique}@test.com"
        
        # Register user
        reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "test123456",
            "name": f"Test Provider {unique}",
            "role": "provider"
        })
        if reg_response.status_code != 200:
            pytest.skip(f"Could not create test provider user: {reg_response.text}")
        
        token = reg_response.json()["token"]
        user = reg_response.json()["user"]
        
        # Create provider profile
        provider_data = {
            "business_name": f"Test Carer {unique}",
            "description": "Test provider for client reviews",
            "phone": "+56912345678",
            "comuna": "Santiago",
            "address": "Test Address 123",
            "services_offered": [
                {
                    "service_type": "paseo",
                    "price_from": 10000,
                    "description": "Paseo de perros",
                    "pet_sizes": ["pequeno", "mediano"]
                }
            ]
        }
        
        prov_response = requests.post(
            f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {token}"},
            json=provider_data
        )
        if prov_response.status_code != 200:
            pytest.skip(f"Could not create provider profile: {prov_response.text}")
        
        provider = prov_response.json()
        print(f"✓ Created test provider: {provider['provider_id']}")
        
        return {"token": token, "user": user, "provider": provider}

    @pytest.fixture(scope="class")
    def client_user(self):
        """Create a client user to be reviewed"""
        unique = uuid.uuid4().hex[:6]
        email = f"client_test_{unique}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "test123456",
            "name": f"Test Client {unique}",
            "role": "client"
        })
        if response.status_code != 200:
            pytest.skip(f"Could not create test client user: {response.text}")
        
        data = response.json()
        print(f"✓ Created test client: {data['user']['user_id']}")
        return {"token": data["token"], "user": data["user"]}

    def test_admin_cannot_review_client(self, admin_token, client_user):
        """POST /api/reviews/client returns 403 if user is not a provider"""
        response = requests.post(
            f"{BASE_URL}/api/reviews/client",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "client_user_id": client_user["user"]["user_id"],
                "rating": 5,
                "punctuality": 5,
                "pet_behavior": 5,
                "communication": 5,
                "comment": "Test review"
            }
        )
        assert response.status_code == 403, f"Expected 403 for non-provider, got {response.status_code}"
        data = response.json()
        assert "cuidadores" in data.get("detail", "").lower() or "provider" in data.get("detail", "").lower()
        print("✓ POST /api/reviews/client returns 403 for non-provider (admin)")

    def test_provider_can_create_client_review(self, provider_token_and_data, client_user):
        """POST /api/reviews/client creates a client review with sub-ratings"""
        review_data = {
            "client_user_id": client_user["user"]["user_id"],
            "rating": 4,
            "punctuality": 5,
            "pet_behavior": 4,
            "communication": 5,
            "comment": "Great client! Very punctual and their pet was well-behaved."
        }
        
        response = requests.post(
            f"{BASE_URL}/api/reviews/client",
            headers={"Authorization": f"Bearer {provider_token_and_data['token']}"},
            json=review_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "review_id" in data
        assert data["client_user_id"] == client_user["user"]["user_id"]
        assert data["rating"] == review_data["rating"]
        assert data["punctuality"] == review_data["punctuality"]
        assert data["pet_behavior"] == review_data["pet_behavior"]
        assert data["communication"] == review_data["communication"]
        assert data["comment"] == review_data["comment"]
        assert "provider_user_id" in data
        assert "provider_id" in data
        assert "provider_name" in data
        print(f"✓ POST /api/reviews/client created review: {data['review_id']}")
        
        return data

    def test_cannot_review_same_client_twice(self, provider_token_and_data, client_user):
        """POST /api/reviews/client returns 400 if already reviewed"""
        # The previous test already created a review, so this should fail
        review_data = {
            "client_user_id": client_user["user"]["user_id"],
            "rating": 3,
            "punctuality": 3,
            "pet_behavior": 3,
            "communication": 3,
            "comment": "Duplicate review attempt"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/reviews/client",
            headers={"Authorization": f"Bearer {provider_token_and_data['token']}"},
            json=review_data
        )
        assert response.status_code == 400, f"Expected 400 for duplicate review, got {response.status_code}"
        print("✓ POST /api/reviews/client returns 400 for duplicate review")

    def test_get_client_reviews_by_user_id(self, provider_token_and_data, client_user):
        """GET /api/reviews/client/{user_id} returns reviews for a client"""
        response = requests.get(
            f"{BASE_URL}/api/reviews/client/{client_user['user']['user_id']}",
            headers={"Authorization": f"Bearer {provider_token_and_data['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "client" in data
        assert "reviews" in data
        assert isinstance(data["reviews"], list)
        assert len(data["reviews"]) >= 1
        
        # Verify review structure
        review = data["reviews"][0]
        assert "review_id" in review
        assert "rating" in review
        assert "punctuality" in review
        assert "pet_behavior" in review
        assert "communication" in review
        print(f"✓ GET /api/reviews/client/{client_user['user']['user_id']} returned {len(data['reviews'])} reviews")

    def test_get_my_client_reviews(self, provider_token_and_data, client_user):
        """GET /api/reviews/client/me returns reviews about current user as client"""
        # First ensure the review was created (in case tests run out of order)
        # Check if review already exists
        check_response = requests.get(
            f"{BASE_URL}/api/reviews/client/me",
            headers={"Authorization": f"Bearer {client_user['token']}"}
        )
        
        # If no reviews exist, create one first
        if check_response.status_code == 200 and isinstance(check_response.json(), list) and len(check_response.json()) == 0:
            # Create a review first
            requests.post(
                f"{BASE_URL}/api/reviews/client",
                headers={"Authorization": f"Bearer {provider_token_and_data['token']}"},
                json={
                    "client_user_id": client_user["user"]["user_id"],
                    "rating": 4,
                    "punctuality": 5,
                    "pet_behavior": 4,
                    "communication": 5,
                    "comment": "Test review for /me endpoint"
                }
            )
        
        response = requests.get(
            f"{BASE_URL}/api/reviews/client/me",
            headers={"Authorization": f"Bearer {client_user['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"
        # The client should have been reviewed by the provider
        assert len(data) >= 1, f"Expected at least 1 review, got {len(data)}"
        
        # Verify review structure
        review = data[0]
        assert "review_id" in review
        assert "rating" in review
        assert "provider_name" in review
        print(f"✓ GET /api/reviews/client/me returned {len(data)} reviews for client")

    def test_get_reviews_given_by_provider(self, provider_token_and_data):
        """GET /api/reviews/provider/given returns reviews given by current provider"""
        response = requests.get(
            f"{BASE_URL}/api/reviews/provider/given",
            headers={"Authorization": f"Bearer {provider_token_and_data['token']}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Verify review structure with client info
        review = data[0]
        assert "review_id" in review
        assert "client_user_id" in review
        assert "rating" in review
        print(f"✓ GET /api/reviews/provider/given returned {len(data)} reviews")

    def test_non_provider_cannot_get_given_reviews(self, admin_token):
        """GET /api/reviews/provider/given returns 403 for non-provider"""
        response = requests.get(
            f"{BASE_URL}/api/reviews/provider/given",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 403
        print("✓ GET /api/reviews/provider/given returns 403 for non-provider")

    def test_client_reviews_require_auth(self):
        """Client review endpoints require authentication"""
        # POST without auth
        response = requests.post(f"{BASE_URL}/api/reviews/client", json={
            "client_user_id": "test",
            "rating": 5
        })
        assert response.status_code == 401
        
        # GET without auth
        response = requests.get(f"{BASE_URL}/api/reviews/client/test_user_id")
        assert response.status_code == 401
        
        response = requests.get(f"{BASE_URL}/api/reviews/client/me")
        assert response.status_code == 401
        
        response = requests.get(f"{BASE_URL}/api/reviews/provider/given")
        assert response.status_code == 401
        
        print("✓ Client review endpoints require authentication")


class TestClientReviewRatingValidation:
    """Test rating validation for client reviews"""

    @pytest.fixture(scope="class")
    def provider_token(self):
        """Create a provider user for testing"""
        unique = uuid.uuid4().hex[:6]
        email = f"provider_val_{unique}@test.com"
        
        reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email,
            "password": "test123456",
            "name": f"Validation Provider {unique}",
            "role": "provider"
        })
        if reg_response.status_code != 200:
            pytest.skip("Could not create provider user")
        
        token = reg_response.json()["token"]
        
        # Create provider profile
        prov_response = requests.post(
            f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "business_name": f"Val Provider {unique}",
                "phone": "+56912345678",
                "comuna": "Santiago",
                "address": "Test Address"
            }
        )
        if prov_response.status_code != 200:
            pytest.skip("Could not create provider profile")
        
        return token

    def test_rating_must_be_1_to_5(self, provider_token):
        """Ratings must be between 1 and 5"""
        # Create a client to review
        unique = uuid.uuid4().hex[:6]
        client_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"val_client_{unique}@test.com",
            "password": "test123456",
            "name": f"Validation Client {unique}"
        })
        if client_response.status_code != 200:
            pytest.skip("Could not create client")
        
        client_user_id = client_response.json()["user"]["user_id"]
        
        # Try rating of 0 (should fail)
        response = requests.post(
            f"{BASE_URL}/api/reviews/client",
            headers={"Authorization": f"Bearer {provider_token}"},
            json={
                "client_user_id": client_user_id,
                "rating": 0,
                "punctuality": 3,
                "pet_behavior": 3,
                "communication": 3
            }
        )
        assert response.status_code == 422, f"Rating 0 should be invalid, got {response.status_code}"
        
        # Try rating of 6 (should fail)
        response = requests.post(
            f"{BASE_URL}/api/reviews/client",
            headers={"Authorization": f"Bearer {provider_token}"},
            json={
                "client_user_id": client_user_id,
                "rating": 6,
                "punctuality": 3,
                "pet_behavior": 3,
                "communication": 3
            }
        )
        assert response.status_code == 422, f"Rating 6 should be invalid, got {response.status_code}"
        print("✓ Rating validation works (1-5 range enforced)")


class TestRegressionEndpoints:
    """Regression tests for existing functionality"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json()["token"]

    def test_auth_me(self, auth_token):
        """GET /api/auth/me returns current user (regression)"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        print(f"✓ GET /api/auth/me returned user: {data['email']}")

    def test_get_pets(self, auth_token):
        """GET /api/pets returns user's pets (regression)"""
        response = requests.get(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/pets returned {len(data)} pets")

    def test_get_favorites(self, auth_token):
        """GET /api/favorites returns user's favorites (regression)"""
        response = requests.get(
            f"{BASE_URL}/api/favorites",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/favorites returned {len(data)} favorites")

    def test_get_providers(self, auth_token):
        """GET /api/providers returns provider list (regression)"""
        response = requests.get(
            f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/providers returned {len(data)} providers")

    def test_get_subscription_plans(self):
        """GET /api/subscription/plans returns plans (regression)"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/subscription/plans returned {len(data)} plans")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
