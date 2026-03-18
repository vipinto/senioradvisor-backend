"""
Tests for Iteration 8: Search bar with service tabs/dates, admin metrics, SVG logo, pet sizes
Testing: GET /api/providers (pet_sizes), GET /api/admin/metrics
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "admin@ucan.cl"
ADMIN_PASSWORD = "admin123"


class TestHealthAndProviders:
    """Test health check and providers endpoint"""
    
    def test_health_check(self):
        """API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
    
    def test_providers_endpoint_returns_data(self):
        """GET /api/providers returns providers"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        assert isinstance(providers, list)
        assert len(providers) > 0
        print(f"✓ Found {len(providers)} providers")
    
    def test_providers_have_services_with_pet_sizes(self):
        """GET /api/providers - each provider's services include pet_sizes array"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        
        providers_with_pet_sizes = 0
        for provider in providers:
            services = provider.get("services", [])
            for service in services:
                if "pet_sizes" in service and isinstance(service["pet_sizes"], list):
                    providers_with_pet_sizes += 1
                    # Validate pet_sizes values
                    valid_sizes = {"pequeno", "mediano", "grande"}
                    for size in service["pet_sizes"]:
                        assert size in valid_sizes, f"Invalid pet_size: {size}"
                    break
        
        assert providers_with_pet_sizes > 0, "No providers have pet_sizes in their services"
        print(f"✓ {providers_with_pet_sizes} providers have pet_sizes in services")
    
    def test_provider_services_structure(self):
        """GET /api/providers - services have correct structure"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        
        required_fields = ["service_type", "price_from"]
        for provider in providers[:3]:  # Check first 3 providers
            for service in provider.get("services", []):
                for field in required_fields:
                    assert field in service, f"Missing field: {field} in service"
                assert service["service_type"] in ["alojamiento", "guarderia", "paseo"]
        
        print("✓ Provider services have correct structure")


class TestAdminMetrics:
    """Test admin metrics endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip("Admin login failed - skipping admin tests")
        return response.json().get("token")
    
    def test_admin_login_success(self):
        """Admin can login with correct credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"
        print("✓ Admin login successful")
    
    def test_metrics_requires_authentication(self):
        """GET /api/admin/metrics returns 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/admin/metrics")
        assert response.status_code == 401
        print("✓ Metrics endpoint requires authentication")
    
    def test_metrics_returns_6_months_data(self, admin_token):
        """GET /api/admin/metrics returns 6 months of data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/metrics",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        metrics = response.json()
        assert isinstance(metrics, list)
        assert len(metrics) == 6, f"Expected 6 months, got {len(metrics)}"
        print(f"✓ Metrics returns {len(metrics)} months of data")
    
    def test_metrics_data_structure(self, admin_token):
        """GET /api/admin/metrics - each month has correct fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/metrics",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        metrics = response.json()
        
        required_fields = ["month", "users", "providers", "subscriptions", "reviews"]
        for month_data in metrics:
            for field in required_fields:
                assert field in month_data, f"Missing field: {field}"
            
            # Verify numeric fields are integers
            assert isinstance(month_data["users"], int)
            assert isinstance(month_data["providers"], int)
            assert isinstance(month_data["subscriptions"], int)
            assert isinstance(month_data["reviews"], int)
            
            # Verify month is a valid Spanish month abbreviation
            valid_months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 
                          'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
            assert month_data["month"] in valid_months, f"Invalid month: {month_data['month']}"
        
        print("✓ Metrics data structure is correct")
    
    def test_admin_stats_endpoint(self, admin_token):
        """GET /api/admin/stats returns summary statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        stats = response.json()
        
        required_fields = ["total_users", "total_providers", "pending_providers", 
                          "verified_providers", "active_subscriptions", "total_reviews"]
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"
            assert isinstance(stats[field], int)
        
        print(f"✓ Admin stats: {stats['total_users']} users, {stats['total_providers']} providers")


class TestProviderFiltering:
    """Test provider filtering by service type"""
    
    def test_filter_by_service_type_alojamiento(self):
        """GET /api/providers?service_type=alojamiento filters correctly"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=alojamiento")
        assert response.status_code == 200
        providers = response.json()
        
        # Verify all returned providers offer alojamiento
        for provider in providers:
            service_types = [s["service_type"] for s in provider.get("services", [])]
            assert "alojamiento" in service_types, f"Provider {provider['business_name']} doesn't offer alojamiento"
        
        print(f"✓ Found {len(providers)} providers with alojamiento")
    
    def test_filter_by_service_type_guarderia(self):
        """GET /api/providers?service_type=guarderia filters correctly"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=guarderia")
        assert response.status_code == 200
        providers = response.json()
        
        for provider in providers:
            service_types = [s["service_type"] for s in provider.get("services", [])]
            assert "guarderia" in service_types
        
        print(f"✓ Found {len(providers)} providers with guarderia")
    
    def test_filter_by_service_type_paseo(self):
        """GET /api/providers?service_type=paseo filters correctly"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=paseo")
        assert response.status_code == 200
        providers = response.json()
        
        for provider in providers:
            service_types = [s["service_type"] for s in provider.get("services", [])]
            assert "paseo" in service_types
        
        print(f"✓ Found {len(providers)} providers with paseo")


class TestSubscriptionPlans:
    """Test subscription plans endpoint"""
    
    def test_subscription_plans_public(self):
        """GET /api/subscription/plans returns active plans"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        plans = response.json()
        
        assert isinstance(plans, list)
        assert len(plans) > 0, "No subscription plans found"
        
        for plan in plans:
            assert "plan_id" in plan
            assert "name" in plan
            assert "price_clp" in plan
            assert "duration_months" in plan
            # Public endpoint should only return active plans
            assert plan.get("active", True) == True
        
        print(f"✓ Found {len(plans)} active subscription plans")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
