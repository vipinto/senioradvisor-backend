"""
Backend tests for iteration 13 - Testing new features:
1. Two registration flows (client vs carer) - frontend only
2. Pet registration (CRUD): POST /pets, GET /pets, DELETE /pets/{pet_id}
3. Pet photo upload: POST /pets/upload-photo
4. Profile photo upload: POST /profile/upload-photo
5. SOS config (admin): GET /admin/sos, PUT /admin/sos
6. SOS info (authenticated): GET /sos/info
7. Provider approved=true by default
8. Regression: login, providers list, subscription plans
"""
import pytest
import requests
import os
import uuid
from io import BytesIO

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@ucan.cl"
ADMIN_PASSWORD = "admin123"


class TestHealthAndAuth:
    """Basic health check and authentication tests"""

    def test_health_check(self):
        """API health endpoint should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")

    def test_admin_login(self):
        """Login as admin user"""
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
        return data["token"]


class TestPetCRUD:
    """Pet CRUD operations tests"""

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

    def test_get_pets(self, auth_token):
        """GET /api/pets returns user's pets"""
        response = requests.get(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/pets returned {len(data)} pets")

    def test_create_pet(self, auth_token):
        """POST /api/pets creates a pet with all fields"""
        test_pet = {
            "name": f"TestPet_{uuid.uuid4().hex[:6]}",
            "breed": "Labrador",
            "size": "grande",
            "sex": "macho",
            "age": 3,
            "species": "perro"
        }
        response = requests.post(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=test_pet
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_pet["name"]
        assert data["breed"] == test_pet["breed"]
        assert data["size"] == test_pet["size"]
        assert data["sex"] == test_pet["sex"]
        assert data["age"] == test_pet["age"]
        assert "pet_id" in data
        print(f"✓ POST /api/pets created pet: {data['pet_id']}")
        return data["pet_id"]

    def test_create_and_verify_pet_persistence(self, auth_token):
        """Create pet and verify it persists with GET"""
        # Create
        test_pet = {
            "name": f"PersistTest_{uuid.uuid4().hex[:6]}",
            "breed": "Beagle",
            "size": "mediano",
            "sex": "hembra",
            "age": 2
        }
        create_response = requests.post(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=test_pet
        )
        assert create_response.status_code == 200
        created_pet = create_response.json()
        pet_id = created_pet["pet_id"]
        
        # Verify with GET
        get_response = requests.get(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert get_response.status_code == 200
        pets = get_response.json()
        found_pet = next((p for p in pets if p["pet_id"] == pet_id), None)
        assert found_pet is not None, f"Created pet {pet_id} not found in GET response"
        assert found_pet["name"] == test_pet["name"]
        assert found_pet["breed"] == test_pet["breed"]
        print(f"✓ Pet persistence verified: {pet_id}")
        
        # Cleanup: delete the test pet
        requests.delete(
            f"{BASE_URL}/api/pets/{pet_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

    def test_delete_pet(self, auth_token):
        """DELETE /api/pets/{pet_id} removes a pet"""
        # First create a pet to delete
        test_pet = {"name": f"ToDelete_{uuid.uuid4().hex[:6]}", "size": "pequeno", "sex": "macho"}
        create_response = requests.post(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=test_pet
        )
        assert create_response.status_code == 200
        pet_id = create_response.json()["pet_id"]
        
        # Delete
        delete_response = requests.delete(
            f"{BASE_URL}/api/pets/{pet_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert delete_response.status_code == 200
        
        # Verify deletion
        get_response = requests.get(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        pets = get_response.json()
        assert not any(p["pet_id"] == pet_id for p in pets), "Pet still exists after deletion"
        print(f"✓ DELETE /api/pets/{pet_id} successfully removed pet")

    def test_delete_nonexistent_pet(self, auth_token):
        """DELETE /api/pets/{pet_id} returns 404 for non-existent pet"""
        response = requests.delete(
            f"{BASE_URL}/api/pets/nonexistent_pet_id",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
        print("✓ DELETE non-existent pet returns 404")

    def test_pets_require_auth(self):
        """Pets endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/pets")
        assert response.status_code == 401
        print("✓ GET /api/pets without auth returns 401")


class TestPhotoUpload:
    """Photo upload tests for pets and profile"""

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

    def test_upload_pet_photo(self, auth_token):
        """POST /api/pets/upload-photo uploads a pet photo"""
        # Create a fake image file (1x1 pixel PNG)
        fake_image = BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
        
        response = requests.post(
            f"{BASE_URL}/api/pets/upload-photo",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"file": ("test_pet.png", fake_image, "image/png")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "/uploads/pets/" in data["url"]
        print(f"✓ Pet photo uploaded: {data['url']}")

    def test_upload_profile_photo(self, auth_token):
        """POST /api/profile/upload-photo uploads and updates user profile photo"""
        # Create a fake image file
        fake_image = BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
        
        response = requests.post(
            f"{BASE_URL}/api/profile/upload-photo",
            headers={"Authorization": f"Bearer {auth_token}"},
            files={"file": ("profile.png", fake_image, "image/png")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "/uploads/profiles/" in data["url"]
        print(f"✓ Profile photo uploaded: {data['url']}")

    def test_photo_upload_requires_auth(self):
        """Photo upload endpoints require authentication"""
        fake_image = BytesIO(b'fake image data')
        
        pet_response = requests.post(
            f"{BASE_URL}/api/pets/upload-photo",
            files={"file": ("test.png", fake_image, "image/png")}
        )
        assert pet_response.status_code == 401
        
        profile_response = requests.post(
            f"{BASE_URL}/api/profile/upload-photo",
            files={"file": ("test.png", fake_image, "image/png")}
        )
        assert profile_response.status_code == 401
        print("✓ Photo upload endpoints require auth")


class TestSOSConfig:
    """SOS configuration tests (admin only)"""

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

    def test_get_sos_config_admin(self, admin_token):
        """GET /api/admin/sos returns SOS config for admin"""
        response = requests.get(
            f"{BASE_URL}/api/admin/sos",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should have these fields even if empty
        assert "active" in data
        print(f"✓ GET /api/admin/sos returned config: active={data.get('active')}")

    def test_update_sos_config(self, admin_token):
        """PUT /api/admin/sos updates SOS config"""
        test_config = {
            "active": True,
            "phone": "+56912345678",
            "schedule": "Lunes a Viernes 9:00-18:00",
            "vet_name": "Dr. Test Veterinario"
        }
        response = requests.put(
            f"{BASE_URL}/api/admin/sos",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=test_config
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("active") == True
        assert data.get("phone") == test_config["phone"]
        print("✓ PUT /api/admin/sos updated config successfully")
        
        # Verify persistence
        get_response = requests.get(
            f"{BASE_URL}/api/admin/sos",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched.get("phone") == test_config["phone"]
        assert fetched.get("vet_name") == test_config["vet_name"]
        print("✓ SOS config persistence verified")

    def test_get_sos_info_authenticated(self, admin_token):
        """GET /api/sos/info returns SOS info for authenticated users"""
        response = requests.get(
            f"{BASE_URL}/api/sos/info",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "active" in data
        if data.get("active"):
            assert "phone" in data
        print(f"✓ GET /api/sos/info returned: active={data.get('active')}")

    def test_sos_info_requires_auth(self):
        """GET /api/sos/info requires authentication"""
        response = requests.get(f"{BASE_URL}/api/sos/info")
        assert response.status_code == 401
        print("✓ GET /api/sos/info requires auth")

    def test_sos_admin_requires_admin_role(self):
        """Admin SOS endpoints require admin role"""
        # Create a regular user
        unique = uuid.uuid4().hex[:6]
        reg_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"sos_test_{unique}@test.com",
            "password": "test123456",
            "name": "SOS Tester"
        })
        if reg_response.status_code != 200:
            pytest.skip("Could not create test user")
        
        user_token = reg_response.json()["token"]
        
        # Try to access admin SOS endpoint
        response = requests.get(
            f"{BASE_URL}/api/admin/sos",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}"
        print("✓ Admin SOS endpoints require admin role")


class TestProviderApproval:
    """Test that providers are approved by default"""

    @pytest.fixture(scope="class")
    def new_user_token(self):
        """Create and login as a new user"""
        unique = uuid.uuid4().hex[:6]
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"provider_test_{unique}@test.com",
            "password": "test123456",
            "name": "Provider Tester"
        })
        if response.status_code != 200:
            pytest.skip("Could not create test user")
        return response.json()["token"]

    def test_provider_approved_by_default(self, new_user_token):
        """Creating a provider sets approved=true by default"""
        provider_data = {
            "business_name": f"Test Provider {uuid.uuid4().hex[:6]}",
            "description": "Test provider for iteration 13",
            "phone": "+56912345678",
            "comuna": "Santiago",
            "services_offered": [
                {
                    "service_type": "paseo",
                    "price_from": 10000,
                    "description": "Paseo de perros",
                    "pet_sizes": ["pequeno", "mediano"]
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {new_user_token}"},
            json=provider_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("approved") == True, "Provider should be approved by default"
        assert "approved_at" in data, "Provider should have approved_at timestamp"
        print(f"✓ Provider created with approved=true: {data['provider_id']}")


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

    def test_get_providers(self, auth_token):
        """GET /api/providers returns provider list"""
        response = requests.get(
            f"{BASE_URL}/api/providers",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/providers returned {len(data)} providers")

    def test_get_subscription_plans(self):
        """GET /api/subscription/plans returns plans"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/subscription/plans returned {len(data)} plans")

    def test_auth_me(self, auth_token):
        """GET /api/auth/me returns current user"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        print(f"✓ GET /api/auth/me returned user: {data['email']}")

    def test_invalid_login(self):
        """Invalid login credentials return 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid login returns 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
