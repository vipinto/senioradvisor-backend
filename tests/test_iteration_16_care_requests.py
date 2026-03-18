"""
Test iteration 16: Care Requests System
- POST /api/care-requests: create care request (client only)
- GET /api/care-requests/my-requests: view my requests (client)
- GET /api/care-requests: view client requests (provider)
- PUT /api/care-requests/{id}: pause/activate request
- DELETE /api/care-requests/{id}: delete request
- GET /api/subscription/plans: should return only 1 active plan at $9,990
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@ucan.cl", "password": "admin123"}
PROVIDER_CREDS = {"email": "test_provider_ui@test.com", "password": "test123456"}
CLIENT_CREDS = {"email": "test_client_ui@test.com", "password": "test123456"}


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


@pytest.fixture(scope="module")
def client_token():
    """Get client token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json=CLIENT_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Client authentication failed")


@pytest.fixture(scope="module")
def client_pet_id(client_token):
    """Get or create a pet for the client to use in care requests"""
    headers = {"Authorization": f"Bearer {client_token}"}
    
    # First, try to get existing pets
    response = requests.get(f"{BASE_URL}/api/pets", headers=headers)
    if response.status_code == 200:
        pets = response.json()
        if pets:
            return pets[0]["pet_id"]
    
    # Create a pet if none exists
    pet_data = {
        "name": f"TEST_Pet_{uuid.uuid4().hex[:6]}",
        "species": "perro",
        "breed": "Labrador",
        "size": "mediano",
        "sex": "macho",
        "age": 3
    }
    response = requests.post(f"{BASE_URL}/api/pets", headers=headers, json=pet_data)
    if response.status_code in [200, 201]:
        return response.json().get("pet_id")
    pytest.skip("Could not get or create pet for testing")


class TestSubscriptionPlans:
    """Test subscription plans endpoint - should return single plan at $9,990"""
    
    def test_get_subscription_plans_returns_single_plan(self):
        """GET /api/subscription/plans should return exactly 1 active plan"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        plans = response.json()
        assert isinstance(plans, list), "Response should be a list"
        
        # Filter active plans
        active_plans = [p for p in plans if p.get("active")]
        assert len(active_plans) == 1, f"Expected 1 active plan, got {len(active_plans)}"
        
        plan = active_plans[0]
        assert plan["price_clp"] == 9990, f"Expected price 9990, got {plan['price_clp']}"
        assert "Suscripción U-CAN" in plan.get("name", ""), f"Plan name mismatch: {plan.get('name')}"


class TestCareRequestsCreate:
    """Test care request creation (POST /api/care-requests)"""
    
    def test_create_care_request_requires_auth(self):
        """POST /api/care-requests should require authentication"""
        response = requests.post(f"{BASE_URL}/api/care-requests", json={
            "pet_id": "fake_pet",
            "service_type": "paseo",
            "description": "Test",
            "comuna": "Santiago"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_create_care_request_success(self, client_token, client_pet_id):
        """POST /api/care-requests should create a care request"""
        headers = {"Authorization": f"Bearer {client_token}"}
        request_data = {
            "pet_id": client_pet_id,
            "service_type": "paseo",
            "description": "TEST_Necesito alguien que pasee a mi perro por las mañanas",
            "comuna": "Providencia",
            "flexible_dates": True
        }
        
        response = requests.post(f"{BASE_URL}/api/care-requests", headers=headers, json=request_data)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "request_id" in data, "Response should contain request_id"
        assert data["service_type"] == "paseo"
        assert data["status"] == "active"
        assert data["comuna"] == "Providencia"
        assert data["flexible_dates"] == True
        
        # Store for later cleanup
        TestCareRequestsCreate.created_request_id = data["request_id"]
    
    def test_create_care_request_invalid_pet(self, client_token):
        """POST /api/care-requests with invalid pet_id should fail"""
        headers = {"Authorization": f"Bearer {client_token}"}
        request_data = {
            "pet_id": "nonexistent_pet_id",
            "service_type": "cuidado",
            "description": "Test request",
            "comuna": "Las Condes"
        }
        
        response = requests.post(f"{BASE_URL}/api/care-requests", headers=headers, json=request_data)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestCareRequestsMyRequests:
    """Test GET /api/care-requests/my-requests (client viewing their own requests)"""
    
    def test_my_requests_requires_auth(self):
        """GET /api/care-requests/my-requests should require authentication"""
        response = requests.get(f"{BASE_URL}/api/care-requests/my-requests")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_my_requests_returns_list(self, client_token):
        """GET /api/care-requests/my-requests should return client's requests"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/care-requests/my-requests", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"


class TestCareRequestsProviderView:
    """Test GET /api/care-requests (provider viewing client requests)"""
    
    def test_care_requests_requires_auth(self):
        """GET /api/care-requests should require authentication"""
        response = requests.get(f"{BASE_URL}/api/care-requests")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
    
    def test_care_requests_requires_provider_role(self, client_token):
        """GET /api/care-requests should only work for providers"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.get(f"{BASE_URL}/api/care-requests", headers=headers)
        
        # Should return 403 because client is not a provider
        assert response.status_code == 403, f"Expected 403 for non-provider, got {response.status_code}"
    
    def test_care_requests_provider_access(self, provider_token):
        """GET /api/care-requests should work for providers"""
        headers = {"Authorization": f"Bearer {provider_token}"}
        response = requests.get(f"{BASE_URL}/api/care-requests", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Provider without subscription should see contact_hidden=True
        if data:
            first_request = data[0]
            # Check that the request has expected fields
            assert "request_id" in first_request
            assert "service_type" in first_request
            assert "comuna" in first_request
    
    def test_care_requests_filter_by_service_type(self, provider_token):
        """GET /api/care-requests?service_type=paseo should filter by service type"""
        headers = {"Authorization": f"Bearer {provider_token}"}
        response = requests.get(f"{BASE_URL}/api/care-requests?service_type=paseo", headers=headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # All returned requests should be of type paseo
        for req in data:
            assert req["service_type"] == "paseo", f"Expected paseo, got {req['service_type']}"


class TestCareRequestsUpdate:
    """Test PUT /api/care-requests/{id} (pause/activate request)"""
    
    def test_update_care_request_pause(self, client_token, client_pet_id):
        """PUT /api/care-requests/{id} should allow pausing a request"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # First create a request to update
        create_data = {
            "pet_id": client_pet_id,
            "service_type": "daycare",
            "description": "TEST_Daycare request for testing updates",
            "comuna": "Vitacura"
        }
        create_response = requests.post(f"{BASE_URL}/api/care-requests", headers=headers, json=create_data)
        assert create_response.status_code in [200, 201], f"Failed to create: {create_response.text}"
        
        request_id = create_response.json()["request_id"]
        
        # Now update to pause
        update_data = {"status": "paused"}
        update_response = requests.put(f"{BASE_URL}/api/care-requests/{request_id}", headers=headers, json=update_data)
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}"
        updated = update_response.json()
        assert updated["status"] == "paused", f"Expected status paused, got {updated['status']}"
        
        # Cleanup - store for deletion
        TestCareRequestsUpdate.request_to_delete = request_id
    
    def test_update_care_request_activate(self, client_token):
        """PUT /api/care-requests/{id} should allow activating a paused request"""
        if not hasattr(TestCareRequestsUpdate, 'request_to_delete'):
            pytest.skip("No request to update")
        
        headers = {"Authorization": f"Bearer {client_token}"}
        request_id = TestCareRequestsUpdate.request_to_delete
        
        update_data = {"status": "active"}
        response = requests.put(f"{BASE_URL}/api/care-requests/{request_id}", headers=headers, json=update_data)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        updated = response.json()
        assert updated["status"] == "active", f"Expected status active, got {updated['status']}"
    
    def test_update_nonexistent_request(self, client_token):
        """PUT /api/care-requests/{id} with invalid id should return 404"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.put(f"{BASE_URL}/api/care-requests/nonexistent_id", headers=headers, json={"status": "paused"})
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestCareRequestsDelete:
    """Test DELETE /api/care-requests/{id}"""
    
    def test_delete_care_request(self, client_token, client_pet_id):
        """DELETE /api/care-requests/{id} should delete a request"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # Create a request to delete
        create_data = {
            "pet_id": client_pet_id,
            "service_type": "cuidado",
            "description": "TEST_Request to be deleted",
            "comuna": "Nunoa"
        }
        create_response = requests.post(f"{BASE_URL}/api/care-requests", headers=headers, json=create_data)
        assert create_response.status_code in [200, 201], f"Failed to create: {create_response.text}"
        
        request_id = create_response.json()["request_id"]
        
        # Delete it
        delete_response = requests.delete(f"{BASE_URL}/api/care-requests/{request_id}", headers=headers)
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}"
        
        # Verify it's gone
        get_response = requests.get(f"{BASE_URL}/api/care-requests/{request_id}", headers=headers)
        assert get_response.status_code == 404, "Request should be deleted"
    
    def test_delete_nonexistent_request(self, client_token):
        """DELETE /api/care-requests/{id} with invalid id should return 404"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = requests.delete(f"{BASE_URL}/api/care-requests/nonexistent_id", headers=headers)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_created_requests(self, client_token):
        """Delete any TEST_ prefixed requests created during tests"""
        headers = {"Authorization": f"Bearer {client_token}"}
        
        # Get all my requests
        response = requests.get(f"{BASE_URL}/api/care-requests/my-requests", headers=headers)
        if response.status_code == 200:
            requests_list = response.json()
            for req in requests_list:
                if req.get("description", "").startswith("TEST_"):
                    delete_resp = requests.delete(f"{BASE_URL}/api/care-requests/{req['request_id']}", headers=headers)
                    print(f"Cleaned up request {req['request_id']}: {delete_resp.status_code}")
        
        # Always pass cleanup
        assert True
