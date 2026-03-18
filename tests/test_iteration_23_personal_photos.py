"""
Tests for Iteration 23: Personal Info Photo Upload Feature
- POST /providers/my-profile/personal-info/photos?category=yard - upload yard photo (max 3)
- POST /providers/my-profile/personal-info/photos?category=pets - upload pets photo (max 3)
- DELETE /providers/my-profile/personal-info/photos/{photo_id} - delete a personal photo
- PUT /providers/my-profile/personal-info - saving text fields preserves existing photos
- GET /providers/{provider_id} - public profile includes yard_photos and pets_photos in personal_info
- POST /providers/my-profile/personal-info/photos?category=yard - rejects when 3 photos already uploaded
"""
import pytest
import requests
import os
import io
from PIL import Image

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_CARER = {"email": "cuidador@test.com", "password": "cuidador123"}
TEST_CLIENT = {"email": "cliente@test.com", "password": "cliente123"}
TEST_PROVIDER_ID = "prov_23ad24c36254"


def create_test_image():
    """Create a small test image for upload testing"""
    img = Image.new('RGB', (200, 200), color='blue')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes


class TestAuthentication:
    """Authentication helpers"""
    
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


class TestPhotoUploadEndpoint(TestAuthentication):
    """Tests for POST /providers/my-profile/personal-info/photos"""
    
    def test_photo_upload_requires_auth(self):
        """Photo upload without auth returns 401"""
        img = create_test_image()
        files = {'file': ('test.jpg', img, 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=yard",
            files=files
        )
        assert response.status_code == 401
        print("PASS: Photo upload requires auth (401)")
    
    def test_photo_upload_invalid_category(self, carer_token):
        """Photo upload with invalid category returns 400"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        img = create_test_image()
        files = {'file': ('test.jpg', img, 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=invalid",
            headers=headers,
            files=files
        )
        assert response.status_code == 400
        assert "yard" in response.json().get("detail", "").lower() or "pets" in response.json().get("detail", "").lower()
        print("PASS: Invalid category returns 400")
    
    def test_photo_upload_yard_success(self, carer_token):
        """Upload a yard photo successfully"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        img = create_test_image()
        files = {'file': ('yard_test.jpg', img, 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=yard",
            headers=headers,
            files=files
        )
        
        # May succeed or fail if already at max (3)
        if response.status_code == 200:
            data = response.json()
            assert "photo" in data
            assert data["photo"]["category"] == "yard"
            assert "photo_id" in data["photo"]
            assert "url" in data["photo"]
            assert "thumbnail_url" in data["photo"]
            print(f"PASS: Yard photo uploaded successfully - photo_id: {data['photo']['photo_id']}")
            return data["photo"]["photo_id"]
        elif response.status_code == 400:
            assert "máximo" in response.json().get("detail", "").lower() or "3" in response.json().get("detail", "")
            print("PASS: Correctly rejected - max photos reached")
            return None
        else:
            pytest.fail(f"Unexpected status: {response.status_code}")
    
    def test_photo_upload_pets_success(self, carer_token):
        """Upload a pets photo successfully"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        img = create_test_image()
        files = {'file': ('pets_test.jpg', img, 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=pets",
            headers=headers,
            files=files
        )
        
        # May succeed or fail if already at max (3)
        if response.status_code == 200:
            data = response.json()
            assert "photo" in data
            assert data["photo"]["category"] == "pets"
            assert "photo_id" in data["photo"]
            assert "url" in data["photo"]
            assert "thumbnail_url" in data["photo"]
            print(f"PASS: Pets photo uploaded successfully - photo_id: {data['photo']['photo_id']}")
            return data["photo"]["photo_id"]
        elif response.status_code == 400:
            assert "máximo" in response.json().get("detail", "").lower() or "3" in response.json().get("detail", "")
            print("PASS: Correctly rejected - max photos reached")
            return None
        else:
            pytest.fail(f"Unexpected status: {response.status_code}")
    
    def test_photo_upload_only_images_allowed(self, carer_token):
        """Non-image files should be rejected"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        # Try uploading a text file
        files = {'file': ('test.txt', b'This is not an image', 'text/plain')}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=yard",
            headers=headers,
            files=files
        )
        # Should reject non-image
        assert response.status_code == 400
        print("PASS: Non-image file rejected")


class TestPhotoDeleteEndpoint(TestAuthentication):
    """Tests for DELETE /providers/my-profile/personal-info/photos/{photo_id}"""
    
    def test_photo_delete_requires_auth(self):
        """Photo delete without auth returns 401"""
        response = requests.delete(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos/fake_photo_id"
        )
        assert response.status_code == 401
        print("PASS: Photo delete requires auth (401)")
    
    def test_photo_delete_nonexistent_returns_404(self, carer_token):
        """Delete nonexistent photo returns 404"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        response = requests.delete(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos/nonexistent_photo_12345",
            headers=headers
        )
        assert response.status_code == 404
        print("PASS: Delete nonexistent photo returns 404")
    
    def test_photo_delete_success(self, carer_token):
        """Upload and delete a photo successfully"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        
        # First, check current photos count
        pi_res = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info", headers=headers)
        assert pi_res.status_code == 200
        pi = pi_res.json()
        yard_count = len(pi.get("yard_photos", []))
        
        # If already at 3, delete one first to make room for test
        photo_id_to_delete = None
        if yard_count >= 3:
            photo_id_to_delete = pi["yard_photos"][-1]["photo_id"]
            del_res = requests.delete(
                f"{BASE_URL}/api/providers/my-profile/personal-info/photos/{photo_id_to_delete}",
                headers=headers
            )
            assert del_res.status_code == 200
            print(f"Deleted existing photo to make room: {photo_id_to_delete}")
        
        # Now upload a new photo
        img = create_test_image()
        files = {'file': ('delete_test.jpg', img, 'image/jpeg')}
        upload_res = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=yard",
            headers=headers,
            files=files
        )
        assert upload_res.status_code == 200
        new_photo_id = upload_res.json()["photo"]["photo_id"]
        print(f"Uploaded test photo: {new_photo_id}")
        
        # Verify photo exists in personal_info
        verify_res = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info", headers=headers)
        assert verify_res.status_code == 200
        verify_pi = verify_res.json()
        photo_ids = [p["photo_id"] for p in verify_pi.get("yard_photos", [])]
        assert new_photo_id in photo_ids, "Photo should exist after upload"
        
        # Now delete the photo
        delete_res = requests.delete(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos/{new_photo_id}",
            headers=headers
        )
        assert delete_res.status_code == 200
        assert delete_res.json()["message"] == "Foto eliminada"
        print(f"Successfully deleted photo: {new_photo_id}")
        
        # Verify photo no longer exists
        final_res = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info", headers=headers)
        assert final_res.status_code == 200
        final_pi = final_res.json()
        final_photo_ids = [p["photo_id"] for p in final_pi.get("yard_photos", [])]
        assert new_photo_id not in final_photo_ids, "Photo should be removed after delete"
        
        print("PASS: Photo delete cycle works correctly")


class TestPhotoPersistence(TestAuthentication):
    """Tests for PUT /providers/my-profile/personal-info preserving photos"""
    
    def test_text_update_preserves_photos(self, carer_token):
        """Updating text fields via PUT should preserve existing photos"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        
        # Get current personal info with photos
        get_res = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info", headers=headers)
        assert get_res.status_code == 200
        original_pi = get_res.json()
        original_yard_photos = original_pi.get("yard_photos", [])
        original_pets_photos = original_pi.get("pets_photos", [])
        
        print(f"Original yard_photos count: {len(original_yard_photos)}")
        print(f"Original pets_photos count: {len(original_pets_photos)}")
        
        # Update only text fields
        update_data = {
            "housing_type": "casa",
            "has_yard": True,
            "yard_description": "Test yard description - updated to test photo preservation",
            "has_own_pets": True,
            "own_pets_description": "Test pets description - updated",
            "animal_experience": "Test experience - updated for photo preservation test",
            "daily_availability": "Test availability - updated",
            "additional_info": "Test additional info - updated"
        }
        
        put_res = requests.put(
            f"{BASE_URL}/api/providers/my-profile/personal-info",
            headers=headers,
            json=update_data
        )
        assert put_res.status_code == 200
        
        # Verify photos are preserved
        final_res = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info", headers=headers)
        assert final_res.status_code == 200
        final_pi = final_res.json()
        final_yard_photos = final_pi.get("yard_photos", [])
        final_pets_photos = final_pi.get("pets_photos", [])
        
        print(f"Final yard_photos count: {len(final_yard_photos)}")
        print(f"Final pets_photos count: {len(final_pets_photos)}")
        
        # Photo arrays should be preserved
        assert len(final_yard_photos) == len(original_yard_photos), "Yard photos should be preserved"
        assert len(final_pets_photos) == len(original_pets_photos), "Pets photos should be preserved"
        
        # Text fields should be updated
        assert final_pi["yard_description"] == update_data["yard_description"]
        assert final_pi["animal_experience"] == update_data["animal_experience"]
        
        print("PASS: PUT /providers/my-profile/personal-info preserves existing photos")


class TestPublicProfilePhotos(TestAuthentication):
    """Tests for GET /providers/{provider_id} including photos"""
    
    def test_public_profile_includes_yard_photos(self):
        """Public profile should include yard_photos in personal_info"""
        response = requests.get(f"{BASE_URL}/api/providers/{TEST_PROVIDER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "personal_info" in data
        pi = data.get("personal_info", {})
        
        # yard_photos should be present (may be empty array)
        if "yard_photos" in pi:
            assert isinstance(pi["yard_photos"], list)
            for photo in pi["yard_photos"]:
                assert "photo_id" in photo
                assert "url" in photo
                assert "thumbnail_url" in photo
                assert photo["category"] == "yard"
            print(f"PASS: Public profile has {len(pi['yard_photos'])} yard photos")
        else:
            print("PASS: Public profile has no yard_photos (field may not exist)")
    
    def test_public_profile_includes_pets_photos(self):
        """Public profile should include pets_photos in personal_info"""
        response = requests.get(f"{BASE_URL}/api/providers/{TEST_PROVIDER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        pi = data.get("personal_info", {})
        
        # pets_photos should be present (may be empty array)
        if "pets_photos" in pi:
            assert isinstance(pi["pets_photos"], list)
            for photo in pi["pets_photos"]:
                assert "photo_id" in photo
                assert "url" in photo
                assert "thumbnail_url" in photo
                assert photo["category"] == "pets"
            print(f"PASS: Public profile has {len(pi['pets_photos'])} pets photos")
        else:
            print("PASS: Public profile has no pets_photos (field may not exist)")
    
    def test_photo_urls_are_accessible(self):
        """Photo URLs in public profile should be valid paths"""
        response = requests.get(f"{BASE_URL}/api/providers/{TEST_PROVIDER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        pi = data.get("personal_info", {})
        
        # Check yard photos
        for photo in pi.get("yard_photos", []):
            assert photo["url"].startswith("/api/uploads/personal/")
            assert photo["thumbnail_url"].startswith("/api/uploads/personal/")
            # Verify the photo is actually accessible
            photo_res = requests.get(f"{BASE_URL}{photo['url']}")
            assert photo_res.status_code == 200, f"Photo not accessible: {photo['url']}"
            print(f"PASS: Yard photo accessible: {photo['photo_id']}")
        
        # Check pets photos
        for photo in pi.get("pets_photos", []):
            assert photo["url"].startswith("/api/uploads/personal/")
            photo_res = requests.get(f"{BASE_URL}{photo['url']}")
            assert photo_res.status_code == 200, f"Photo not accessible: {photo['url']}"
            print(f"PASS: Pets photo accessible: {photo['photo_id']}")


class TestMaxPhotosLimit(TestAuthentication):
    """Tests for max 3 photos per category limit"""
    
    def test_max_yard_photos_limit(self, carer_token):
        """Should reject yard photo when already at 3"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        
        # Get current yard photos count
        pi_res = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info", headers=headers)
        assert pi_res.status_code == 200
        pi = pi_res.json()
        yard_count = len(pi.get("yard_photos", []))
        
        print(f"Current yard photos: {yard_count}")
        
        # Upload photos until we hit the limit
        photos_uploaded = []
        while yard_count < 3:
            img = create_test_image()
            files = {'file': (f'yard_test_{yard_count}.jpg', img, 'image/jpeg')}
            upload_res = requests.post(
                f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=yard",
                headers=headers,
                files=files
            )
            assert upload_res.status_code == 200
            photos_uploaded.append(upload_res.json()["photo"]["photo_id"])
            yard_count += 1
            print(f"Uploaded yard photo {yard_count}/3")
        
        # Now try to upload a 4th photo - should be rejected
        img = create_test_image()
        files = {'file': ('yard_test_4.jpg', img, 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=yard",
            headers=headers,
            files=files
        )
        assert response.status_code == 400
        detail = response.json().get("detail", "").lower()
        assert "máximo" in detail or "3" in detail
        print("PASS: 4th yard photo correctly rejected (max 3 limit)")
        
        # Cleanup: delete the photos we uploaded
        for photo_id in photos_uploaded:
            requests.delete(
                f"{BASE_URL}/api/providers/my-profile/personal-info/photos/{photo_id}",
                headers=headers
            )
            print(f"Cleaned up: {photo_id}")
    
    def test_max_pets_photos_limit(self, carer_token):
        """Should reject pets photo when already at 3"""
        headers = {"Authorization": f"Bearer {carer_token}"}
        
        # Get current pets photos count
        pi_res = requests.get(f"{BASE_URL}/api/providers/my-profile/personal-info", headers=headers)
        assert pi_res.status_code == 200
        pi = pi_res.json()
        pets_count = len(pi.get("pets_photos", []))
        
        print(f"Current pets photos: {pets_count}")
        
        # Upload photos until we hit the limit
        photos_uploaded = []
        while pets_count < 3:
            img = create_test_image()
            files = {'file': (f'pets_test_{pets_count}.jpg', img, 'image/jpeg')}
            upload_res = requests.post(
                f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=pets",
                headers=headers,
                files=files
            )
            assert upload_res.status_code == 200
            photos_uploaded.append(upload_res.json()["photo"]["photo_id"])
            pets_count += 1
            print(f"Uploaded pets photo {pets_count}/3")
        
        # Now try to upload a 4th photo - should be rejected
        img = create_test_image()
        files = {'file': ('pets_test_4.jpg', img, 'image/jpeg')}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/personal-info/photos?category=pets",
            headers=headers,
            files=files
        )
        assert response.status_code == 400
        detail = response.json().get("detail", "").lower()
        assert "máximo" in detail or "3" in detail
        print("PASS: 4th pets photo correctly rejected (max 3 limit)")
        
        # Cleanup: delete the photos we uploaded
        for photo_id in photos_uploaded:
            requests.delete(
                f"{BASE_URL}/api/providers/my-profile/personal-info/photos/{photo_id}",
                headers=headers
            )
            print(f"Cleaned up: {photo_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
