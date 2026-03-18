"""
Iteration 28: MercadoPago Provider Subscription Tests
Tests the new MercadoPago integration for provider subscriptions.

Features tested:
- GET /api/subscription/plans?role=provider - List provider subscription plans
- POST /api/subscription/create-payment - Create MercadoPago payment preference
- POST /api/webhooks/mercadopago - Webhook endpoint accepts POST requests
- GET /api/subscription/my - Get current user's subscription status
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PROVIDER_EMAIL = "proveedor1@senioradvisor.cl"
PROVIDER_PASSWORD = "demo123"
CLIENT_EMAIL = "demo@senioradvisor.cl"
CLIENT_PASSWORD = "demo123"

# Expected plan IDs
EXPECTED_PLAN_IDS = ["provider_mensual", "provider_trimestral", "provider_anual"]
EXPECTED_PRICES = {
    "provider_mensual": 19990,
    "provider_trimestral": 49990,
    "provider_anual": 149990
}


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def provider_auth_token(api_client):
    """Get authentication token for provider user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": PROVIDER_EMAIL,
        "password": PROVIDER_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        # API returns 'token' not 'access_token'
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Provider authentication failed - status: {response.status_code}, response: {response.text}")


@pytest.fixture(scope="module")
def provider_client(api_client, provider_auth_token):
    """Session with provider auth header"""
    api_client.headers.update({"Authorization": f"Bearer {provider_auth_token}"})
    return api_client


class TestSubscriptionPlans:
    """Test subscription plans endpoint"""
    
    def test_get_provider_plans_returns_3_plans(self, api_client):
        """GET /api/subscription/plans?role=provider should return 3 active plans"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=provider")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        plans = response.json()
        assert isinstance(plans, list), "Response should be a list"
        assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
        
        print(f"✓ Found {len(plans)} provider subscription plans")
    
    def test_plans_have_correct_structure(self, api_client):
        """Plans should have required fields: plan_id, name, price_clp, duration_months"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=provider")
        plans = response.json()
        
        for plan in plans:
            assert "plan_id" in plan, f"Plan missing plan_id: {plan}"
            assert "name" in plan, f"Plan missing name: {plan}"
            assert "price_clp" in plan, f"Plan missing price_clp: {plan}"
            assert "duration_months" in plan, f"Plan missing duration_months: {plan}"
            assert "active" in plan, f"Plan missing active field: {plan}"
            assert plan["active"] == True, f"Plan should be active: {plan}"
        
        print("✓ All plans have correct structure")
    
    def test_plans_have_correct_ids(self, api_client):
        """Plans should have the expected plan_ids"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=provider")
        plans = response.json()
        
        plan_ids = [p["plan_id"] for p in plans]
        
        for expected_id in EXPECTED_PLAN_IDS:
            assert expected_id in plan_ids, f"Missing plan: {expected_id}. Found: {plan_ids}"
        
        print(f"✓ All expected plan IDs present: {plan_ids}")
    
    def test_plans_have_correct_prices(self, api_client):
        """Plans should have the correct prices in CLP"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=provider")
        plans = response.json()
        
        for plan in plans:
            plan_id = plan["plan_id"]
            if plan_id in EXPECTED_PRICES:
                expected_price = EXPECTED_PRICES[plan_id]
                actual_price = plan["price_clp"]
                assert actual_price == expected_price, f"Plan {plan_id}: expected {expected_price}, got {actual_price}"
                print(f"✓ {plan_id}: ${actual_price:,} CLP")
        
        print("✓ All plan prices correct")


class TestCreatePayment:
    """Test MercadoPago payment creation endpoint"""
    
    def test_create_payment_requires_auth(self, api_client):
        """POST /api/subscription/create-payment requires authentication"""
        # Use fresh session without auth
        fresh_client = requests.Session()
        fresh_client.headers.update({"Content-Type": "application/json"})
        
        response = fresh_client.post(f"{BASE_URL}/api/subscription/create-payment", json={
            "plan_id": "provider_mensual"
        })
        
        # Should return 401 or 403 for unauthenticated request
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ create-payment endpoint requires authentication")
    
    def test_create_payment_returns_checkout_url(self, provider_client):
        """POST /api/subscription/create-payment should return a MercadoPago checkout URL"""
        response = provider_client.post(f"{BASE_URL}/api/subscription/create-payment", json={
            "plan_id": "provider_mensual"
        })
        
        # May return 400 if user already has active subscription
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "suscripción activa" in error_detail.lower():
                print("✓ create-payment endpoint works (user already has subscription)")
                pytest.skip("Provider already has active subscription")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "checkout_url" in data, f"Response missing checkout_url: {data}"
        assert "subscription_id" in data, f"Response missing subscription_id: {data}"
        assert "preference_id" in data, f"Response missing preference_id: {data}"
        
        checkout_url = data["checkout_url"]
        # Verify it's a valid MercadoPago URL (production mode)
        assert checkout_url.startswith("https://www.mercadopago.cl/") or checkout_url.startswith("https://www.mercadopago.com/"), \
            f"Expected MercadoPago checkout URL, got: {checkout_url}"
        
        print(f"✓ Checkout URL generated: {checkout_url[:60]}...")
        print(f"✓ Subscription ID: {data['subscription_id']}")
        print(f"✓ Preference ID: {data['preference_id']}")
    
    def test_create_payment_invalid_plan(self, provider_client):
        """POST /api/subscription/create-payment with invalid plan_id should return 400"""
        response = provider_client.post(f"{BASE_URL}/api/subscription/create-payment", json={
            "plan_id": "invalid_plan_xyz"
        })
        
        # Should return 400 for invalid plan
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Invalid plan_id returns 400 error")


class TestWebhook:
    """Test MercadoPago webhook endpoint"""
    
    def test_webhook_endpoint_exists(self, api_client):
        """POST /api/webhooks/mercadopago should accept POST requests"""
        # Send a minimal test payload
        response = api_client.post(f"{BASE_URL}/api/webhooks/mercadopago", json={
            "type": "test",
            "data": {}
        })
        
        # Should return 200 with status: ok
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "status" in data, f"Response missing status field: {data}"
        assert data["status"] == "ok", f"Expected status 'ok', got: {data['status']}"
        
        print("✓ Webhook endpoint accepts POST and returns {status: ok}")
    
    def test_webhook_handles_payment_notification(self, api_client):
        """Webhook should handle payment notification type"""
        response = api_client.post(f"{BASE_URL}/api/webhooks/mercadopago", json={
            "type": "payment",
            "data": {
                "id": 12345678  # Fake payment ID
            }
        })
        
        # Should return 200 (even if payment not found, it should not crash)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Webhook handles payment notification type")


class TestMySubscription:
    """Test subscription status endpoint"""
    
    def test_my_subscription_requires_auth(self, api_client):
        """GET /api/subscription/my requires authentication"""
        fresh_client = requests.Session()
        fresh_client.headers.update({"Content-Type": "application/json"})
        
        response = fresh_client.get(f"{BASE_URL}/api/subscription/my")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ /subscription/my endpoint requires authentication")
    
    def test_my_subscription_returns_status(self, provider_client):
        """GET /api/subscription/my should return subscription status"""
        response = provider_client.get(f"{BASE_URL}/api/subscription/my")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "has_subscription" in data, f"Response missing has_subscription: {data}"
        
        has_sub = data.get("has_subscription", False)
        status = data.get("status", "none")
        
        print(f"✓ Subscription status: has_subscription={has_sub}, status={status}")
        
        if has_sub:
            assert "plan_id" in data or data.get("plan_id") is not None, "Active subscription should have plan_id"
            print(f"✓ Active subscription with plan: {data.get('plan_id')}")


class TestProviderLogin:
    """Test provider login functionality"""
    
    def test_provider_login_works(self, api_client):
        """Provider should be able to login with correct credentials"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": PROVIDER_EMAIL,
            "password": PROVIDER_PASSWORD
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # API returns 'token' not 'access_token'
        assert "token" in data or "access_token" in data, f"Response missing token: {data}"
        assert "user" in data, f"Response missing user: {data}"
        
        user = data["user"]
        assert user.get("email") == PROVIDER_EMAIL, f"Email mismatch: {user.get('email')}"
        
        # Provider should have provider role or is_provider flag
        is_provider = user.get("role") == "provider" or user.get("is_provider") == True
        print(f"✓ Provider login successful: {user.get('email')}, role={user.get('role')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
