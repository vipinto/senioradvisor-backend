"""
Backend API Tests for U-CAN Payment/Subscription Features
Tests for Mercado Pago integration and subscription endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSubscriptionPlansEndpoint:
    """Tests for GET /api/subscription/plans - Returns 3 plans with prices"""
    
    def test_get_subscription_plans_returns_three_plans(self):
        """Test that subscription plans endpoint returns exactly 3 plans"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        
        # Should return exactly 3 plans
        assert isinstance(data, list)
        assert len(data) == 3, f"Expected 3 plans, got {len(data)}"
        print(f"✓ Found {len(data)} subscription plans")
    
    def test_subscription_plans_have_prices(self):
        """Test that all plans have prices in CLP"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        
        expected_prices = {9990, 24990, 79990}
        actual_prices = set()
        
        for plan in data:
            assert "price_clp" in plan, "Plan should have price_clp"
            assert plan["price_clp"] > 0, "Price should be positive"
            actual_prices.add(plan["price_clp"])
            print(f"  - {plan['name']}: ${plan['price_clp']} CLP")
        
        assert actual_prices == expected_prices, f"Unexpected prices: {actual_prices}"
        print("✓ All 3 plans have correct prices")
    
    def test_subscription_plans_have_required_fields(self):
        """Test that all plans have all required fields"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["plan_id", "name", "duration_months", "price_clp", "features"]
        
        for plan in data:
            for field in required_fields:
                assert field in plan, f"Plan missing field: {field}"
            assert isinstance(plan["features"], list), "Features should be a list"
            assert len(plan["features"]) > 0, "Plan should have at least one feature"
        
        print("✓ All plans have required fields")
    
    def test_subscription_plans_have_plan_ids(self):
        """Test that plans have correct plan_id format"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        
        expected_plan_ids = {"plan_1month", "plan_3months", "plan_12months"}
        actual_plan_ids = {plan["plan_id"] for plan in data}
        
        assert actual_plan_ids == expected_plan_ids, f"Unexpected plan IDs: {actual_plan_ids}"
        print("✓ All plan IDs are correct")
    
    def test_popular_plan_marked(self):
        """Test that the 3-month plan is marked as popular"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        
        popular_plans = [p for p in data if p.get("popular") == True]
        assert len(popular_plans) >= 1, "Should have at least one popular plan"
        
        # The 3-month plan should be popular
        three_month_plan = next((p for p in data if p["plan_id"] == "plan_3months"), None)
        assert three_month_plan is not None, "Should have 3-month plan"
        assert three_month_plan.get("popular") == True, "3-month plan should be marked as popular"
        print("✓ 3-month plan is marked as popular")


class TestMercadoPagoWebhookEndpoint:
    """Tests for POST /api/webhooks/mercadopago - Webhook endpoint responds ok"""
    
    def test_webhook_endpoint_exists(self):
        """Test that webhook endpoint accepts POST requests"""
        # Send a valid webhook payload structure
        payload = {
            "type": "payment",
            "data": {
                "id": "12345"
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhooks/mercadopago", json=payload)
        
        # Should return 200 with status ok (even if payment doesn't exist)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data, "Response should have status field"
        print(f"✓ Webhook endpoint responds with: {data}")
    
    def test_webhook_handles_empty_payload(self):
        """Test that webhook handles empty/malformed payloads gracefully"""
        response = requests.post(f"{BASE_URL}/api/webhooks/mercadopago", json={})
        
        # Should not crash, return some response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data
        print(f"✓ Webhook handles empty payload: {data}")
    
    def test_webhook_handles_non_payment_type(self):
        """Test that webhook handles non-payment notification types"""
        payload = {
            "type": "merchant_order",
            "data": {
                "id": "67890"
            }
        }
        response = requests.post(f"{BASE_URL}/api/webhooks/mercadopago", json=payload)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Webhook handles non-payment notification types")


class TestCreatePaymentEndpoint:
    """Tests for POST /api/subscription/create-payment - Requires authentication"""
    
    def test_create_payment_requires_auth(self):
        """Test that create payment endpoint requires authentication"""
        payload = {
            "plan_id": "plan_1month"
        }
        response = requests.post(f"{BASE_URL}/api/subscription/create-payment", json=payload)
        
        # Should return 401 Unauthorized without auth
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Create payment endpoint requires authentication")


class TestSubscriptionMyEndpoint:
    """Tests for GET /api/subscription/my - Requires authentication"""
    
    def test_my_subscription_requires_auth(self):
        """Test that my subscription endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/my")
        
        # Should return 401 Unauthorized without auth
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ My subscription endpoint requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
