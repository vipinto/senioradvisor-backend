"""
Regression tests after backend refactoring.
Tests all main API endpoints to ensure functionality was not broken during refactor.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Shared session state
class TestState:
    admin_token = None
    test_user_email = None
    test_user_token = None


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ============= HEALTH CHECK =============

class TestHealthCheck:
    """Health check tests - should run first"""
    
    def test_health_endpoint(self, api_client):
        """GET /api/health returns healthy status"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "U-CAN"
        print(f"✓ Health check passed: {data}")


# ============= AUTH ENDPOINTS (prefix: /auth) =============

class TestAuthEndpoints:
    """Tests for auth_routes.py endpoints"""
    
    def test_login_admin_success(self, api_client):
        """POST /api/auth/login with admin credentials"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "admin@ucan.cl"
        TestState.admin_token = data["token"]
        print(f"✓ Admin login successful, role: {data['user'].get('role')}")
    
    def test_login_invalid_credentials(self, api_client):
        """POST /api/auth/login with wrong credentials returns 401"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print("✓ Invalid login correctly rejected with 401")
    
    def test_register_new_user(self, api_client):
        """POST /api/auth/register creates new user"""
        unique_email = f"test_refactor_{uuid.uuid4().hex[:8]}@test.com"
        response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": unique_email,
            "password": "test123456",
            "name": "Test Refactor User"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        TestState.test_user_email = unique_email
        TestState.test_user_token = data["token"]
        print(f"✓ New user registered: {unique_email}")
    
    def test_register_short_password(self, api_client):
        """POST /api/auth/register rejects short password"""
        response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"test_short_{uuid.uuid4().hex[:6]}@test.com",
            "password": "123",  # Less than 6 chars
            "name": "Test User"
        })
        assert response.status_code == 400
        print("✓ Short password correctly rejected")
    
    def test_get_me_with_token(self, api_client):
        """GET /api/auth/me with valid token returns user data"""
        assert TestState.admin_token, "Admin token not set"
        response = api_client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "email" in data
        print(f"✓ Get me successful: {data['email']}")
    
    def test_get_me_without_token(self, api_client):
        """GET /api/auth/me without token returns 401"""
        response = api_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ Get me without token correctly rejected")
    
    def test_google_auth_no_params(self, api_client):
        """POST /api/auth/google with no params returns 400"""
        response = api_client.post(f"{BASE_URL}/api/auth/google", json={})
        assert response.status_code == 400
        print("✓ Google auth with no params correctly returns 400")
    
    def test_google_auth_fake_code(self, api_client):
        """POST /api/auth/google with fake code returns error"""
        response = api_client.post(f"{BASE_URL}/api/auth/google", json={
            "code": "fake_code_12345",
            "redirect_uri": "https://image-carousel-13.preview.emergentagent.com/auth/google/callback"
        })
        # Should return 401 for invalid code (expected behavior)
        assert response.status_code in [400, 401]
        print(f"✓ Google auth with fake code returns {response.status_code} (expected)")
    
    def test_forgot_password(self, api_client):
        """POST /api/auth/forgot-password returns message"""
        response = api_client.post(f"{BASE_URL}/api/auth/forgot-password", json={
            "email": "admin@ucan.cl"
        })
        # Could be 200 (email sent) or other status
        assert response.status_code in [200, 404]
        print(f"✓ Forgot password returns status {response.status_code}")
    
    def test_logout(self, api_client):
        """POST /api/auth/logout clears session"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/logout",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("✓ Logout successful")


# ============= PROVIDER ENDPOINTS =============

class TestProviderEndpoints:
    """Tests for provider_routes.py endpoints"""
    
    def test_get_providers_list(self, api_client):
        """GET /api/providers returns list of providers"""
        response = api_client.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} providers")
    
    def test_get_providers_filtered_by_service(self, api_client):
        """GET /api/providers?service_type=paseo filters correctly"""
        response = api_client.get(f"{BASE_URL}/api/providers?service_type=paseo")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Filtered providers by service_type=paseo: {len(data)} results")


# ============= SUBSCRIPTION ENDPOINTS =============

class TestSubscriptionEndpoints:
    """Tests for subscription_routes.py endpoints"""
    
    def test_get_subscription_plans(self, api_client):
        """GET /api/subscription/plans returns active plans"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "plan_id" in data[0]
            assert "name" in data[0]
            assert "price_clp" in data[0]
        print(f"✓ Got {len(data)} subscription plans")


# ============= ADMIN ENDPOINTS (prefix: /admin) =============

class TestAdminEndpoints:
    """Tests for admin_routes.py endpoints"""
    
    def test_admin_stats(self, api_client):
        """GET /api/admin/stats returns dashboard stats"""
        # Re-login to get fresh token since logout was called
        login_resp = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        TestState.admin_token = login_resp.json()["token"]
        
        response = api_client.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_providers" in data
        assert "pending_providers" in data
        print(f"✓ Admin stats: {data['total_users']} users, {data['total_providers']} providers")
    
    def test_admin_metrics(self, api_client):
        """GET /api/admin/metrics returns 6 months of data"""
        response = api_client.get(
            f"{BASE_URL}/api/admin/metrics",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6  # 6 months
        for month in data:
            assert "month" in month
            assert "users" in month
            assert "providers" in month
        print(f"✓ Admin metrics: {len(data)} months of data")
    
    def test_admin_plans(self, api_client):
        """GET /api/admin/plans returns plans list"""
        response = api_client.get(
            f"{BASE_URL}/api/admin/plans",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin plans: {len(data)} plans")


# ============= NOTIFICATION ENDPOINTS =============

class TestNotificationEndpoints:
    """Tests for notification_routes.py endpoints"""
    
    def test_get_notifications(self, api_client):
        """GET /api/notifications returns notifications list"""
        response = api_client.get(
            f"{BASE_URL}/api/notifications",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} notifications")
    
    def test_get_unread_count(self, api_client):
        """GET /api/notifications/unread-count returns count"""
        response = api_client.get(
            f"{BASE_URL}/api/notifications/unread-count",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)
        print(f"✓ Unread notifications count: {data['count']}")


# ============= SOCIAL ENDPOINTS (Favorites) =============

class TestFavoritesEndpoints:
    """Tests for social_routes.py favorites endpoints"""
    
    def test_get_favorites(self, api_client):
        """GET /api/favorites returns favorites list (may be empty)"""
        response = api_client.get(
            f"{BASE_URL}/api/favorites",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} favorites")


# ============= CHAT ENDPOINTS (prefix: /chat) =============

class TestChatEndpoints:
    """Tests for chat_routes.py endpoints"""
    
    def test_get_conversations(self, api_client):
        """GET /api/chat/conversations returns conversations list"""
        response = api_client.get(
            f"{BASE_URL}/api/chat/conversations",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} conversations")


# ============= MISC ENDPOINTS (Pets) =============

class TestMiscEndpoints:
    """Tests for misc_routes.py endpoints"""
    
    def test_get_my_pets(self, api_client):
        """GET /api/pets returns user's pets list"""
        response = api_client.get(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {TestState.admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} pets")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
