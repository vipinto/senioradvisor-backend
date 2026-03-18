"""
Iteration 19 Tests: New Subscription Model and Free Provider Chat Access
Tests the updated subscription model with two plans (Client $9,990 and Provider $7,500)
and free provider chat functionality (respond but not initiate)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@ucan.cl"
ADMIN_PASSWORD = "admin123"
PROVIDER_EMAIL = "cuidador@test.com"  # Free provider (pending subscription)
PROVIDER_PASSWORD = "cuidador123"
CLIENT_EMAIL = "test_client_ui@test.com"
CLIENT_PASSWORD = "test123456"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def provider_auth_token(api_client):
    """Get authentication token for the provider user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": PROVIDER_EMAIL,
        "password": PROVIDER_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Provider authentication failed: {response.text}")


@pytest.fixture(scope="module")
def client_auth_token(api_client):
    """Get authentication token for the client user"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLIENT_EMAIL,
        "password": CLIENT_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Client authentication failed: {response.text}")


@pytest.fixture(scope="module")
def admin_auth_token(api_client):
    """Get authentication token for admin"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Admin authentication failed: {response.text}")


class TestSubscriptionPlansAPI:
    """Test subscription plans API with role-based filtering"""
    
    def test_get_all_active_plans(self, api_client):
        """GET /api/subscription/plans returns all active plans"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) >= 2, "Should have at least 2 plans (client and provider)"
        
        # Verify all returned plans are active
        for plan in plans:
            assert plan.get("active") == True, "All returned plans should be active"
            assert "price_clp" in plan
            assert "plan_id" in plan
        
        print(f"✓ GET /api/subscription/plans returned {len(plans)} active plans")
    
    def test_get_client_plans_only(self, api_client):
        """GET /api/subscription/plans?role=client returns only client plan at $9,990"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=client")
        assert response.status_code == 200
        
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) >= 1, "Should have at least 1 client plan"
        
        # Check all plans have role=client and correct price
        client_plan_found = False
        for plan in plans:
            assert plan.get("role") == "client", f"Plan {plan.get('plan_id')} should have role=client"
            if plan.get("price_clp") == 9990:
                client_plan_found = True
                print(f"✓ Found client plan: {plan.get('plan_id')} at ${plan.get('price_clp')}")
        
        assert client_plan_found, "Should have a client plan at $9,990"
        print(f"✓ GET /api/subscription/plans?role=client returned {len(plans)} client plan(s)")
    
    def test_get_provider_plans_only(self, api_client):
        """GET /api/subscription/plans?role=provider returns only provider plan at $7,500"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=provider")
        assert response.status_code == 200
        
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) >= 1, "Should have at least 1 provider plan"
        
        # Check all plans have role=provider and correct price
        provider_plan_found = False
        for plan in plans:
            assert plan.get("role") == "provider", f"Plan {plan.get('plan_id')} should have role=provider"
            if plan.get("price_clp") == 7500:
                provider_plan_found = True
                print(f"✓ Found provider plan: {plan.get('plan_id')} at ${plan.get('price_clp')}")
        
        assert provider_plan_found, "Should have a provider plan at $7,500"
        print(f"✓ GET /api/subscription/plans?role=provider returned {len(plans)} provider plan(s)")
    
    def test_plan_prices_match_expected_values(self, api_client):
        """Verify the correct prices for client and provider plans"""
        # Client plan
        client_response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=client")
        assert client_response.status_code == 200
        client_plans = client_response.json()
        
        # Provider plan
        provider_response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=provider")
        assert provider_response.status_code == 200
        provider_plans = provider_response.json()
        
        # Verify prices
        client_prices = [p.get("price_clp") for p in client_plans]
        provider_prices = [p.get("price_clp") for p in provider_plans]
        
        assert 9990 in client_prices, f"Client plan should be $9,990, found: {client_prices}"
        assert 7500 in provider_prices, f"Provider plan should be $7,500, found: {provider_prices}"
        
        print(f"✓ Client plan price: $9,990")
        print(f"✓ Provider plan price: $7,500")


class TestFreeProviderChatAccess:
    """Test chat functionality for free providers"""
    
    def test_free_provider_can_get_conversations(self, api_client, provider_auth_token):
        """GET /api/chat/conversations works for free providers"""
        headers = {"Authorization": f"Bearer {provider_auth_token}"}
        
        response = api_client.get(f"{BASE_URL}/api/chat/conversations", headers=headers)
        assert response.status_code == 200
        
        conversations = response.json()
        assert isinstance(conversations, list)
        
        print(f"✓ Free provider can access /api/chat/conversations (found {len(conversations)} conversations)")
    
    def test_free_provider_cannot_initiate_conversation(self, api_client, provider_auth_token):
        """POST /api/chat/messages as free provider initiating conversation returns 403"""
        headers = {"Authorization": f"Bearer {provider_auth_token}"}
        
        # Try to send message to a random user (no prior conversation)
        # Using a test user_id that likely doesn't have a conversation with the provider
        message_data = {
            "receiver_id": "user_nonexistent_test_12345",
            "message": "Test message from free provider"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/chat/messages",
            headers=headers,
            json=message_data
        )
        
        # Should get 403 because free providers can't initiate
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        
        # Check error message mentions Premium
        error_detail = response.json().get("detail", "")
        assert "Premium" in error_detail or "suscripcion" in error_detail.lower(), \
            f"Error should mention Premium subscription: {error_detail}"
        
        print(f"✓ Free provider correctly blocked from initiating conversation (403)")
        print(f"  Error message: {error_detail}")
    
    def test_provider_user_has_no_active_subscription(self, api_client, provider_auth_token):
        """Verify the test provider user is a free provider (no active subscription)"""
        headers = {"Authorization": f"Bearer {provider_auth_token}"}
        
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        
        user_data = response.json()
        assert user_data.get("role") == "provider", "Test user should be a provider"
        
        # Check subscription status - should be false or pending
        has_subscription = user_data.get("has_subscription", False)
        print(f"  User role: {user_data.get('role')}")
        print(f"  Has subscription: {has_subscription}")
        
        # Verify no active subscription
        assert not has_subscription, "Test provider should NOT have an active subscription (should be free)"
        
        print(f"✓ Confirmed provider {PROVIDER_EMAIL} is a free provider (no active subscription)")


class TestFreeClientChatBlocked:
    """Test that free clients cannot access chat"""
    
    def test_free_client_cannot_send_messages(self, api_client, client_auth_token):
        """Free clients cannot send messages (should get 403)"""
        headers = {"Authorization": f"Bearer {client_auth_token}"}
        
        # First check if client has subscription
        me_response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_response.status_code == 200
        
        user_data = me_response.json()
        has_subscription = user_data.get("has_subscription", False)
        
        if has_subscription:
            print(f"⚠ Client has active subscription - cannot test free client message block")
            pytest.skip("Client has active subscription, cannot test free client block")
        
        # Try to send message
        message_data = {
            "receiver_id": "provider_test_12345",
            "message": "Test message from free client"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/chat/messages",
            headers=headers,
            json=message_data
        )
        
        # Should be blocked with 403
        assert response.status_code == 403, f"Expected 403 for free client, got {response.status_code}"
        
        error_detail = response.json().get("detail", "")
        print(f"✓ Free client correctly blocked from sending messages (403)")
        print(f"  Error message: {error_detail}")
    
    def test_client_user_info(self, api_client, client_auth_token):
        """Check client user info to verify subscription status"""
        headers = {"Authorization": f"Bearer {client_auth_token}"}
        
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        
        user_data = response.json()
        print(f"  Client user role: {user_data.get('role')}")
        print(f"  Client has_subscription: {user_data.get('has_subscription')}")
        
        print(f"✓ Client user info retrieved successfully")


class TestSubscriptionPlansDetails:
    """Test detailed subscription plan information"""
    
    def test_all_plans_structure(self, api_client):
        """Verify subscription plans have required fields"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        
        plans = response.json()
        required_fields = ["plan_id", "name", "price_clp", "active"]
        
        for plan in plans:
            for field in required_fields:
                assert field in plan, f"Plan missing required field: {field}"
            
            print(f"  Plan: {plan.get('name')} | Price: ${plan.get('price_clp')} | Role: {plan.get('role', 'N/A')}")
        
        print(f"✓ All {len(plans)} plans have required structure")
    
    def test_plans_sorted_by_price(self, api_client):
        """Verify plans are sorted by price (ascending)"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        
        plans = response.json()
        prices = [p.get("price_clp") for p in plans]
        
        # Check if sorted ascending
        assert prices == sorted(prices), f"Plans should be sorted by price ascending: {prices}"
        
        print(f"✓ Plans sorted by price: {prices}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
