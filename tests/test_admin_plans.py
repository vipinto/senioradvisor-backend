"""
Backend API tests for Admin Plan Management and Subscription Plans
Tests: GET /api/subscription/plans, GET/POST/PUT/DELETE /api/admin/plans, toggle plans
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "admin@ucan.cl"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    return response.json()["token"]


@pytest.fixture
def admin_headers(admin_token):
    """Admin auth headers"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestHealthAndProviders:
    """Basic health and provider endpoints"""

    def test_health_check(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")

    def test_get_providers_returns_data(self):
        """Test GET /api/providers returns providers from Atlas"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should return seed providers from MongoDB Atlas"
        # Verify provider structure
        provider = data[0]
        assert "provider_id" in provider
        assert "business_name" in provider
        assert "comuna" in provider
        print(f"✓ GET /api/providers returned {len(data)} providers")


class TestSubscriptionPlansPublic:
    """Test public subscription plans endpoint"""

    def test_get_subscription_plans_returns_3_plans(self):
        """Test GET /api/subscription/plans returns 3 active plans from database"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
        
        # Verify plans structure and IDs
        plan_ids = [p["plan_id"] for p in plans]
        assert "plan_1month" in plan_ids
        assert "plan_3months" in plan_ids
        assert "plan_12months" in plan_ids
        print(f"✓ GET /api/subscription/plans returned {len(plans)} plans")

    def test_subscription_plans_have_correct_structure(self):
        """Verify subscription plan structure matches database model"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200
        plans = response.json()
        
        for plan in plans:
            # Verify required fields
            assert "plan_id" in plan
            assert "name" in plan
            assert "duration_months" in plan
            assert "price_clp" in plan
            assert "features" in plan
            assert isinstance(plan["features"], list)
            assert "active" in plan
            assert plan["active"] == True  # Public endpoint only returns active
        print("✓ All plans have correct structure")

    def test_subscription_plans_sorted_by_price(self):
        """Verify plans are sorted by price ascending"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        plans = response.json()
        prices = [p["price_clp"] for p in plans]
        assert prices == sorted(prices), "Plans should be sorted by price_clp ascending"
        print("✓ Plans sorted by price correctly")


class TestAuthEndpoints:
    """Test authentication endpoints"""

    def test_admin_login_success(self):
        """Test admin login returns JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"
        print("✓ Admin login successful")

    def test_register_new_user(self):
        """Test user registration"""
        unique_email = f"test_{uuid.uuid4().hex[:8]}@ucan.cl"
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "email": unique_email,
                "password": "testpass123",
                "name": "Test User"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == unique_email
        assert data["user"]["role"] == "client"
        print(f"✓ User registration successful: {unique_email}")


class TestAdminPlansEndpoints:
    """Test admin plan management endpoints"""

    def test_get_admin_plans_requires_auth(self):
        """Test GET /api/admin/plans requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/plans")
        assert response.status_code == 401
        print("✓ GET /api/admin/plans requires auth")

    def test_get_admin_plans_success(self, admin_headers):
        """Test GET /api/admin/plans returns all plans"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        assert response.status_code == 200
        plans = response.json()
        assert isinstance(plans, list)
        assert len(plans) >= 3  # At least 3 seed plans
        print(f"✓ GET /api/admin/plans returned {len(plans)} plans")

    def test_create_plan_success(self, admin_headers):
        """Test POST /api/admin/plans creates new plan"""
        plan_data = {
            "name": f"TEST Plan {uuid.uuid4().hex[:4]}",
            "duration_months": 6,
            "price_clp": 39990,
            "features": ["Feature A", "Feature B"],
            "popular": False
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/plans",
            headers=admin_headers,
            json=plan_data
        )
        assert response.status_code == 200
        created_plan = response.json()
        assert "plan_id" in created_plan
        assert created_plan["name"] == plan_data["name"]
        assert created_plan["duration_months"] == 6
        assert created_plan["price_clp"] == 39990
        assert created_plan["active"] == True
        
        # Cleanup: delete the test plan
        requests.delete(
            f"{BASE_URL}/api/admin/plans/{created_plan['plan_id']}",
            headers=admin_headers
        )
        print(f"✓ Create plan successful: {created_plan['plan_id']}")

    def test_update_plan_success(self, admin_headers):
        """Test PUT /api/admin/plans/{plan_id} updates plan"""
        # First create a test plan
        create_response = requests.post(
            f"{BASE_URL}/api/admin/plans",
            headers=admin_headers,
            json={
                "name": f"TEST Update Plan {uuid.uuid4().hex[:4]}",
                "duration_months": 1,
                "price_clp": 1000,
                "features": ["Original"],
                "popular": False
            }
        )
        plan_id = create_response.json()["plan_id"]
        
        # Update the plan
        update_response = requests.put(
            f"{BASE_URL}/api/admin/plans/{plan_id}",
            headers=admin_headers,
            json={
                "name": "Updated Plan Name",
                "duration_months": 2,
                "price_clp": 2000,
                "features": ["Updated Feature"],
                "popular": True
            }
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["name"] == "Updated Plan Name"
        assert updated["duration_months"] == 2
        assert updated["price_clp"] == 2000
        assert updated["popular"] == True
        assert "updated_at" in updated
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/plans/{plan_id}", headers=admin_headers)
        print(f"✓ Update plan successful")

    def test_toggle_plan_deactivate(self, admin_headers):
        """Test POST /api/admin/plans/{plan_id}/toggle deactivates plan"""
        # Create test plan (active by default)
        create_response = requests.post(
            f"{BASE_URL}/api/admin/plans",
            headers=admin_headers,
            json={
                "name": f"TEST Toggle Plan {uuid.uuid4().hex[:4]}",
                "duration_months": 1,
                "price_clp": 1000,
                "features": [],
                "popular": False
            }
        )
        plan_id = create_response.json()["plan_id"]
        
        # Toggle to deactivate
        toggle_response = requests.post(
            f"{BASE_URL}/api/admin/plans/{plan_id}/toggle",
            headers=admin_headers
        )
        assert toggle_response.status_code == 200
        data = toggle_response.json()
        assert data["active"] == False
        assert "desactivado" in data["message"].lower()
        
        # Toggle again to reactivate
        toggle_response2 = requests.post(
            f"{BASE_URL}/api/admin/plans/{plan_id}/toggle",
            headers=admin_headers
        )
        assert toggle_response2.json()["active"] == True
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/plans/{plan_id}", headers=admin_headers)
        print("✓ Toggle plan successful")

    def test_delete_plan_success(self, admin_headers):
        """Test DELETE /api/admin/plans/{plan_id} removes plan"""
        # Create test plan
        create_response = requests.post(
            f"{BASE_URL}/api/admin/plans",
            headers=admin_headers,
            json={
                "name": f"TEST Delete Plan {uuid.uuid4().hex[:4]}",
                "duration_months": 1,
                "price_clp": 1000,
                "features": [],
                "popular": False
            }
        )
        plan_id = create_response.json()["plan_id"]
        
        # Delete the plan
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/plans/{plan_id}",
            headers=admin_headers
        )
        assert delete_response.status_code == 200
        assert "eliminado" in delete_response.json()["message"].lower()
        
        # Verify plan no longer exists
        update_response = requests.put(
            f"{BASE_URL}/api/admin/plans/{plan_id}",
            headers=admin_headers,
            json={"name": "Should Fail", "duration_months": 1, "price_clp": 1000, "features": [], "popular": False}
        )
        assert update_response.status_code == 404
        print("✓ Delete plan successful")

    def test_delete_nonexistent_plan_returns_404(self, admin_headers):
        """Test DELETE with invalid plan_id returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/plans/plan_nonexistent_xyz123",
            headers=admin_headers
        )
        assert response.status_code == 404
        print("✓ Delete nonexistent plan returns 404")

    def test_regular_user_cannot_access_admin_plans(self):
        """Test regular user cannot access admin endpoints"""
        # Register a regular user
        unique_email = f"regular_{uuid.uuid4().hex[:8]}@ucan.cl"
        reg_response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={"email": unique_email, "password": "testpass123", "name": "Regular User"}
        )
        user_token = reg_response.json()["token"]
        user_headers = {"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"}
        
        # Try to access admin plans
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=user_headers)
        assert response.status_code == 403
        print("✓ Regular user blocked from admin endpoints")


class TestInactivePlansFiltering:
    """Test that inactive plans are filtered from public endpoint"""

    def test_inactive_plans_not_in_public_endpoint(self, admin_headers):
        """Verify inactive plans don't appear in GET /api/subscription/plans"""
        # Create and immediately deactivate a test plan
        create_response = requests.post(
            f"{BASE_URL}/api/admin/plans",
            headers=admin_headers,
            json={
                "name": f"TEST Inactive Plan {uuid.uuid4().hex[:4]}",
                "duration_months": 1,
                "price_clp": 999,
                "features": [],
                "popular": False
            }
        )
        plan_id = create_response.json()["plan_id"]
        
        # Deactivate
        requests.post(f"{BASE_URL}/api/admin/plans/{plan_id}/toggle", headers=admin_headers)
        
        # Check public endpoint doesn't include it
        public_response = requests.get(f"{BASE_URL}/api/subscription/plans")
        public_plans = public_response.json()
        plan_ids = [p["plan_id"] for p in public_plans]
        assert plan_id not in plan_ids, "Inactive plan should not appear in public endpoint"
        
        # But admin endpoint should include it
        admin_response = requests.get(f"{BASE_URL}/api/admin/plans", headers=admin_headers)
        admin_plans = admin_response.json()
        admin_plan_ids = [p["plan_id"] for p in admin_plans]
        assert plan_id in admin_plan_ids, "Inactive plan should appear in admin endpoint"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/admin/plans/{plan_id}", headers=admin_headers)
        print("✓ Inactive plans filtered from public, visible in admin")
