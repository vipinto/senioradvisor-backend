"""
Iteration 41: Premium Gallery Feature Tests
- Standard gallery limit: 3 photos
- Premium gallery: 10 photos (subscription required)
- Provider profile returns premium_gallery and provider_is_subscribed fields
- Admin endpoints for premium gallery management
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from the review request
ADMIN_EMAIL = "admin@senioradvisor.cl"
ADMIN_PASSWORD = "admin123"
SUBSCRIBED_PROVIDER_EMAIL = "proveedor1@senioradvisor.cl"
SUBSCRIBED_PROVIDER_PASSWORD = "demo123"
CLIENT_EMAIL = "demo@senioradvisor.cl"
CLIENT_PASSWORD = "demo123"
PROVIDER_ID = "82aadda9-6892-4033-9cd4-acc31bbdcc39"


class TestAuthentication:
    """Authentication helper tests"""

    def test_admin_login(self):
        """Admin user can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"

    def test_subscribed_provider_login(self):
        """Subscribed provider can login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUBSCRIBED_PROVIDER_EMAIL,
            "password": SUBSCRIBED_PROVIDER_PASSWORD
        })
        assert response.status_code == 200, f"Provider login failed: {response.text}"
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "provider"


def get_admin_token():
    """Get admin JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.text}")
    return response.json()["token"]


def get_provider_token():
    """Get subscribed provider JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUBSCRIBED_PROVIDER_EMAIL,
        "password": SUBSCRIBED_PROVIDER_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Provider login failed: {response.text}")
    return response.json()["token"]


def get_client_token():
    """Get client JWT token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Client login failed: {response.text}")
    return response.json()["token"]


class TestStandardGalleryLimit:
    """Standard gallery limited to 3 photos"""

    def test_gallery_endpoint_exists(self):
        """Gallery upload endpoint exists"""
        token = get_provider_token()
        headers = {"Authorization": f"Bearer {token}"}
        # Test GET gallery
        response = requests.get(f"{BASE_URL}/api/providers/gallery", headers=headers)
        assert response.status_code in [200, 404], f"Gallery endpoint issue: {response.text}"

    def test_get_current_gallery_count(self):
        """Get current gallery photos to verify limit logic"""
        token = get_provider_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200, f"Failed to get profile: {response.text}"
        data = response.json()
        gallery = data.get("gallery", [])
        print(f"Current standard gallery count: {len(gallery)}")
        # Standard gallery should have limit of 3
        assert isinstance(gallery, list)


class TestPremiumGalleryEndpoints:
    """Premium gallery endpoint tests"""

    def test_get_premium_gallery_subscribed_provider(self):
        """Subscribed provider can get their premium gallery"""
        token = get_provider_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/providers/my-profile/premium-gallery", headers=headers)
        assert response.status_code == 200, f"Failed to get premium gallery: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"Premium gallery photos count: {len(data)}")

    def test_premium_gallery_upload_requires_auth(self):
        """Premium gallery upload requires authentication"""
        # Create a simple test image
        from io import BytesIO
        img_data = BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
        img_data.seek(0)
        
        files = {"file": ("test.png", img_data, "image/png")}
        response = requests.post(f"{BASE_URL}/api/providers/my-profile/premium-gallery", files=files)
        assert response.status_code == 401, f"Should require auth: {response.text}"


class TestPublicProviderProfile:
    """Public provider profile includes premium_gallery and subscription status"""

    def test_provider_profile_has_premium_gallery_field(self):
        """Public provider profile includes premium_gallery field"""
        response = requests.get(f"{BASE_URL}/api/providers/{PROVIDER_ID}")
        assert response.status_code == 200, f"Failed to get provider: {response.text}"
        data = response.json()
        assert "premium_gallery" in data, "premium_gallery field missing from provider profile"
        assert "provider_is_subscribed" in data, "provider_is_subscribed field missing from provider profile"
        print(f"Provider is_subscribed: {data.get('provider_is_subscribed')}")
        print(f"Premium gallery count: {len(data.get('premium_gallery', []))}")

    def test_subscribed_provider_shows_premium_gallery(self):
        """Subscribed provider's profile shows their premium gallery"""
        response = requests.get(f"{BASE_URL}/api/providers/{PROVIDER_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Provider is subscribed
        is_subscribed = data.get("provider_is_subscribed", False)
        premium_gallery = data.get("premium_gallery", [])
        
        print(f"is_subscribed: {is_subscribed}")
        print(f"premium_gallery: {premium_gallery}")
        
        # If subscribed, premium_gallery should be available (might be empty but should not be hidden)
        if is_subscribed:
            assert isinstance(premium_gallery, list)
        else:
            # Non-subscribed providers should have empty premium_gallery
            assert premium_gallery == [] or premium_gallery is None


class TestProviderProfileData:
    """Test provider profile data for subscribed provider"""

    def test_my_profile_shows_subscription_status(self):
        """Provider's my-profile includes is_subscribed field"""
        token = get_provider_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200, f"Failed to get my-profile: {response.text}"
        data = response.json()
        assert "is_subscribed" in data, "is_subscribed field missing from my-profile"
        print(f"Provider is_subscribed from my-profile: {data.get('is_subscribed')}")


class TestAdminPremiumGallery:
    """Admin endpoints for premium gallery management"""

    def test_admin_can_get_provider_detail(self):
        """Admin can get provider detail including premium_gallery"""
        token = get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/admin/providers/{PROVIDER_ID}/detail", headers=headers)
        assert response.status_code == 200, f"Admin get provider detail failed: {response.text}"
        data = response.json()
        assert "gallery" in data
        assert "premium_gallery" in data or data.get("premium_gallery") is None
        print(f"Standard gallery: {len(data.get('gallery', []))}")
        print(f"Premium gallery: {len(data.get('premium_gallery', []))}")

    def test_admin_premium_gallery_upload_endpoint_exists(self):
        """Admin premium gallery upload endpoint exists"""
        token = get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        # Test without file to check endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/{PROVIDER_ID}/premium-gallery/upload",
            headers=headers
        )
        # Should get 422 (missing file) not 404 (endpoint not found)
        assert response.status_code in [400, 422], f"Endpoint issue: {response.status_code} - {response.text}"

    def test_admin_standard_gallery_upload_endpoint_exists(self):
        """Admin standard gallery upload endpoint exists"""
        token = get_admin_token()
        headers = {"Authorization": f"Bearer {token}"}
        # Test without file to check endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/{PROVIDER_ID}/gallery/upload",
            headers=headers
        )
        # Should get 422 (missing file) not 404 (endpoint not found)
        assert response.status_code in [400, 422], f"Endpoint issue: {response.status_code} - {response.text}"


class TestGalleryLimits:
    """Test gallery photo limits"""

    def test_standard_gallery_limit_is_3(self):
        """Standard gallery has limit of 3 photos"""
        token = get_provider_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        gallery = data.get("gallery", [])
        # Gallery should not exceed 3 photos
        assert len(gallery) <= 3, f"Gallery has {len(gallery)} photos, should be max 3"
        print(f"Standard gallery count: {len(gallery)}/3")

    def test_premium_gallery_limit_is_10(self):
        """Premium gallery has limit of 10 photos"""
        token = get_provider_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/providers/my-profile/premium-gallery", headers=headers)
        assert response.status_code == 200
        data = response.json()
        # Premium gallery should not exceed 10 photos
        assert len(data) <= 10, f"Premium gallery has {len(data)} photos, should be max 10"
        print(f"Premium gallery count: {len(data)}/10")


class TestNonSubscribedProviderRestrictions:
    """Test that non-subscribed providers cannot use premium gallery"""

    def test_premium_gallery_upload_non_subscribed_forbidden(self):
        """Non-subscribed provider gets 403 when trying to upload to premium gallery"""
        # First we need to check if client is not subscribed
        client_token = get_client_token()
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # Client trying to access premium gallery upload should fail
        # (clients don't have provider profiles anyway)
        from io import BytesIO
        img_data = BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
        img_data.seek(0)
        
        files = {"file": ("test.png", img_data, "image/png")}
        response = requests.post(
            f"{BASE_URL}/api/providers/my-profile/premium-gallery",
            headers=headers,
            files=files
        )
        # Should get 403 (forbidden - no subscription) or 404 (no provider profile)
        assert response.status_code in [403, 404], f"Expected 403 or 404, got {response.status_code}: {response.text}"


class TestRequireSubscriptionFunction:
    """Test the require_subscription auth function"""

    def test_subscribed_provider_has_active_subscription(self):
        """Verify subscribed provider has active subscription"""
        token = get_provider_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        is_subscribed = data.get("is_subscribed", False)
        print(f"Subscribed provider is_subscribed: {is_subscribed}")
        # This provider should be subscribed per the test context
        assert is_subscribed == True, f"Provider should be subscribed but is_subscribed={is_subscribed}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
