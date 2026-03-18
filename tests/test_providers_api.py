"""
Backend API Tests for U-CAN Pet Services Platform
Tests for provider search, provider details, and subscription features
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoint:
    """Health check endpoint tests"""
    
    def test_health_check(self):
        """Test API health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "U-CAN"
        print(f"✓ Health check passed: {data}")


class TestProvidersAPI:
    """Provider endpoints tests - GET /api/providers"""
    
    def test_get_all_providers(self):
        """Test getting all providers returns list with required fields"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one provider"
        print(f"✓ Found {len(data)} providers")
        
        # Validate provider structure
        provider = data[0]
        required_fields = [
            "provider_id", "business_name", "comuna", 
            "latitude", "longitude", "rating", "services"
        ]
        for field in required_fields:
            assert field in provider, f"Missing field: {field}"
        
        print(f"✓ Provider structure validated: {provider['business_name']}")
    
    def test_providers_have_coordinates(self):
        """Test that providers have latitude and longitude for map display"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        providers_with_coords = 0
        for provider in data:
            if provider.get("latitude") and provider.get("longitude"):
                providers_with_coords += 1
                # Validate coordinates are in Chile range
                assert -56 <= provider["latitude"] <= -17, f"Invalid latitude: {provider['latitude']}"
                assert -75 <= provider["longitude"] <= -66, f"Invalid longitude: {provider['longitude']}"
        
        print(f"✓ {providers_with_coords}/{len(data)} providers have valid coordinates")
        assert providers_with_coords > 0, "At least one provider should have coordinates"
    
    def test_providers_have_services(self):
        """Test that providers have services array with required fields"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        for provider in data:
            assert "services" in provider, "Provider should have services array"
            if len(provider["services"]) > 0:
                service = provider["services"][0]
                assert "service_type" in service, "Service should have service_type"
                assert "price_from" in service, "Service should have price_from"
                print(f"✓ {provider['business_name']}: {len(provider['services'])} service(s)")
    
    def test_providers_have_photos(self):
        """Test that providers have photos array for display"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        providers_with_photos = 0
        for provider in data:
            if provider.get("photos") and len(provider["photos"]) > 0:
                providers_with_photos += 1
                # Validate photo URLs
                for photo in provider["photos"]:
                    assert photo.startswith("http"), f"Photo should be URL: {photo}"
        
        print(f"✓ {providers_with_photos}/{len(data)} providers have photos")
    
    def test_providers_have_rating(self):
        """Test that providers have rating fields"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        
        for provider in data:
            assert "rating" in provider, "Provider should have rating"
            assert "total_reviews" in provider, "Provider should have total_reviews"
            # Rating should be between 0 and 5
            assert 0 <= provider["rating"] <= 5, f"Invalid rating: {provider['rating']}"
            print(f"✓ {provider['business_name']}: rating {provider['rating']} ({provider['total_reviews']} reviews)")


class TestSingleProviderAPI:
    """Single provider endpoint tests - GET /api/providers/{id}"""
    
    def test_get_provider_by_id(self):
        """Test getting a single provider by ID"""
        # First get list to get a valid ID
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        assert len(providers) > 0
        
        provider_id = providers[0]["provider_id"]
        
        # Get single provider
        response = requests.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert response.status_code == 200
        provider = response.json()
        
        assert provider["provider_id"] == provider_id
        assert "business_name" in provider
        assert "description" in provider
        assert "services" in provider
        assert "reviews" in provider
        print(f"✓ Got provider: {provider['business_name']}")
    
    def test_provider_has_contact_blocked_for_unauthenticated(self):
        """Test that contact info is blocked for unauthenticated users"""
        # Get a provider
        response = requests.get(f"{BASE_URL}/api/providers")
        providers = response.json()
        provider_id = providers[0]["provider_id"]
        
        # Get single provider without auth
        response = requests.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert response.status_code == 200
        provider = response.json()
        
        # Contact should be blocked
        assert provider.get("contact_blocked") == True, "Contact should be blocked for unauthenticated users"
        assert provider.get("phone") == "******", "Phone should be masked"
        print(f"✓ Contact blocked correctly: phone={provider.get('phone')}, blocked={provider.get('contact_blocked')}")
    
    def test_provider_not_found(self):
        """Test 404 response for non-existent provider"""
        response = requests.get(f"{BASE_URL}/api/providers/invalid_provider_id")
        assert response.status_code == 404
        print("✓ Returns 404 for non-existent provider")


class TestSubscriptionPlansAPI:
    """Subscription plans endpoint tests - GET /api/subscription/plans"""
    
    def test_get_subscription_plans(self):
        """Test getting subscription plans returns list with required fields"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1, "Should have at least one plan"
        print(f"✓ Found {len(data)} subscription plans")
        
        # Validate plan structure
        for plan in data:
            assert "plan_id" in plan, "Plan should have plan_id"
            assert "name" in plan, "Plan should have name"
            assert "price_clp" in plan, "Plan should have price_clp"
            assert "features" in plan, "Plan should have features"
            assert "duration_months" in plan, "Plan should have duration_months"
            print(f"  - {plan['name']}: ${plan['price_clp']} CLP ({plan['duration_months']} months)")


class TestAuthEndpoint:
    """Authentication endpoint tests"""
    
    def test_auth_me_requires_authentication(self):
        """Test that /auth/me returns 401 without authentication"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401, "Should return 401 for unauthenticated request"
        print("✓ Auth endpoint correctly requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
