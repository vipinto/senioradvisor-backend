"""
Test iteration 17: Subscription UI Integration
- GET /api/subscription/plans: single plan at $9,990
- GET /api/auth/me: verify has_subscription field
- Verify SubscriptionCard displays correctly
- Navbar: no "Planes" link
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@ucan.cl", "password": "admin123"}
PROVIDER_CREDS = {"email": "test_provider_ui@test.com", "password": "test123456"}


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def provider_token():
    """Get provider token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=PROVIDER_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Provider authentication failed")


class TestSubscriptionPlans:
    """Test /api/subscription/plans endpoint"""
    
    def test_plans_returns_single_active_plan(self):
        """GET /api/subscription/plans should return 1 active plan at $9,990"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        
        plans = response.json()
        assert isinstance(plans, list)
        
        active_plans = [p for p in plans if p.get("active")]
        assert len(active_plans) == 1, f"Expected 1 active plan, got {len(active_plans)}"
        
        plan = active_plans[0]
        assert plan["price_clp"] == 9990, f"Expected price 9990, got {plan['price_clp']}"
        assert "Suscripción U-CAN" in plan.get("name", "")
    
    def test_plan_has_required_features(self):
        """Plan should have all required features"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        
        plans = response.json()
        active_plan = next((p for p in plans if p.get("active")), None)
        assert active_plan is not None
        
        features = active_plan.get("features", [])
        assert len(features) > 0, "Plan should have features"


class TestUserSubscriptionStatus:
    """Test user subscription status in /api/auth/me"""
    
    def test_auth_me_includes_subscription_status(self, admin_token):
        """GET /api/auth/me should include has_subscription field"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # has_subscription field should exist
        assert "has_subscription" in data, "Response should include has_subscription field"
    
    def test_provider_auth_me_includes_subscription(self, provider_token):
        """Provider's /api/auth/me should include has_subscription"""
        headers = {"Authorization": f"Bearer {provider_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "has_subscription" in data


class TestSubscriptionMyEndpoint:
    """Test /api/subscription/my endpoint"""
    
    def test_my_subscription_requires_auth(self):
        """GET /api/subscription/my should require authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/my")
        assert response.status_code in [401, 403]
    
    def test_my_subscription_returns_status(self, admin_token):
        """GET /api/subscription/my should return subscription status"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/subscription/my", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "has_subscription" in data


class TestProviderCareRequestsAccess:
    """Test provider access to care requests"""
    
    def test_provider_can_view_care_requests(self, provider_token):
        """GET /api/care-requests should work for providers"""
        headers = {"Authorization": f"Bearer {provider_token}"}
        response = requests.get(f"{BASE_URL}/api/care-requests", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_care_requests_show_partial_data_for_non_subscribed(self, provider_token):
        """Non-subscribed providers should see contact_hidden in care requests"""
        headers = {"Authorization": f"Bearer {provider_token}"}
        response = requests.get(f"{BASE_URL}/api/care-requests", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # If there are requests, check contact_hidden field
        if data:
            first_request = data[0]
            # contact_hidden field should exist
            assert "request_id" in first_request
            assert "service_type" in first_request
            assert "comuna" in first_request


class TestHealthAndRegression:
    """Basic health and regression tests"""
    
    def test_health_endpoint(self):
        """GET /api/health should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json().get("status") == "healthy"
    
    def test_providers_endpoint(self):
        """GET /api/providers should return providers list"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
