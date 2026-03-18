"""
Test iteration 20: Proposal System for U-CAN Pet Services
Tests: Create/Get proposals, accept/reject, authorization rules
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from agent_to_agent_context_note
ADMIN_EMAIL = "admin@ucan.cl"
ADMIN_PASSWORD = "admin123"
FREE_PROVIDER_EMAIL = "cuidador@test.com"
FREE_PROVIDER_PASSWORD = "cuidador123"
CLIENT_EMAIL = "test_client_ui@test.com"
CLIENT_PASSWORD = "test123456"


class TestProposalSetup:
    """Setup tests - verify data and create test data if needed"""
    
    @pytest.fixture(scope="class")
    def client_session(self):
        """Login as client and return session"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert res.status_code == 200, f"Client login failed: {res.text}"
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    @pytest.fixture(scope="class")
    def free_provider_session(self):
        """Login as free provider and return session"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": FREE_PROVIDER_EMAIL,
            "password": FREE_PROVIDER_PASSWORD
        })
        assert res.status_code == 200, f"Provider login failed: {res.text}"
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        """Login as admin and return session"""
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session

    def test_client_has_pet(self, client_session):
        """Verify client has pets or create one"""
        res = client_session.get(f"{BASE_URL}/api/pets")
        assert res.status_code == 200
        pets = res.json()
        print(f"Client has {len(pets)} pet(s)")
        
        if len(pets) == 0:
            # Create a test pet
            pet_data = {
                "name": "TEST_Firulais",
                "species": "perro",
                "breed": "Labrador",
                "size": "grande",
                "age": 3,
                "sex": "macho"
            }
            res = client_session.post(f"{BASE_URL}/api/pets", json=pet_data)
            assert res.status_code in [200, 201], f"Failed to create pet: {res.text}"
            print(f"Created test pet: {res.json().get('name')}")
        
        # Return pet_id for other tests
        res = client_session.get(f"{BASE_URL}/api/pets")
        pets = res.json()
        assert len(pets) > 0, "No pets found after creation attempt"
        print(f"Using pet: {pets[0].get('name')} - {pets[0].get('pet_id')}")
        return pets[0].get('pet_id')


class TestCareRequestCreation:
    """Test care request creation (client only)"""
    
    @pytest.fixture(scope="class")
    def client_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    @pytest.fixture(scope="class")
    def client_pet_id(self, client_session):
        """Get or create pet for client"""
        res = client_session.get(f"{BASE_URL}/api/pets")
        pets = res.json()
        
        if len(pets) == 0:
            pet_data = {
                "name": "TEST_Firulais",
                "species": "perro",
                "breed": "Labrador",
                "size": "grande",
                "age": 3,
                "sex": "macho"
            }
            res = client_session.post(f"{BASE_URL}/api/pets", json=pet_data)
            assert res.status_code in [200, 201]
            return res.json().get('pet_id')
        return pets[0].get('pet_id')
    
    def test_create_care_request(self, client_session, client_pet_id):
        """Test POST /api/care-requests (client only)"""
        care_request_data = {
            "pet_id": client_pet_id,
            "service_type": "paseo",
            "description": "TEST_Necesito paseo diario para mi perro en las mananas, 30-45 minutos.",
            "preferred_dates": ["2026-03-10", "2026-03-11", "2026-03-12"],
            "comuna": "Providencia",
            "flexible_dates": True
        }
        
        res = client_session.post(f"{BASE_URL}/api/care-requests", json=care_request_data)
        assert res.status_code in [200, 201], f"Failed to create care request: {res.text}"
        
        data = res.json()
        assert "request_id" in data
        assert data["status"] == "active"
        assert data["service_type"] == "paseo"
        assert data["comuna"] == "Providencia"
        print(f"✓ Created care request: {data['request_id']}")
        return data["request_id"]
    
    def test_get_my_care_requests(self, client_session):
        """Test GET /api/care-requests/my-requests"""
        res = client_session.get(f"{BASE_URL}/api/care-requests/my-requests")
        assert res.status_code == 200
        
        requests_list = res.json()
        assert isinstance(requests_list, list)
        print(f"✓ Client has {len(requests_list)} care request(s)")
        return requests_list


class TestProviderAccessToCareRequests:
    """Test providers can see care requests"""
    
    @pytest.fixture(scope="class")
    def free_provider_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": FREE_PROVIDER_EMAIL,
            "password": FREE_PROVIDER_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    def test_free_provider_can_see_care_requests(self, free_provider_session):
        """Free provider can see care requests (limited info)"""
        res = free_provider_session.get(f"{BASE_URL}/api/care-requests")
        assert res.status_code == 200
        
        requests_list = res.json()
        assert isinstance(requests_list, list)
        print(f"✓ Free provider sees {len(requests_list)} care request(s)")
        
        # Check limited info for non-subscribed
        if len(requests_list) > 0:
            req = requests_list[0]
            assert "contact_hidden" in req
            print(f"  Contact hidden: {req.get('contact_hidden')}")


class TestProposalCreation:
    """Test proposal creation authorization and functionality"""
    
    @pytest.fixture(scope="class")
    def client_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    @pytest.fixture(scope="class")
    def free_provider_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": FREE_PROVIDER_EMAIL,
            "password": FREE_PROVIDER_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    @pytest.fixture(scope="class")
    def care_request_id(self, client_session):
        """Get active care request for testing"""
        # First get existing requests
        res = client_session.get(f"{BASE_URL}/api/care-requests/my-requests")
        requests_list = res.json()
        
        # Find active request
        active_requests = [r for r in requests_list if r.get('status') == 'active']
        
        if len(active_requests) > 0:
            return active_requests[0]['request_id']
        
        # Create new care request if none exist
        # First get pet_id
        pets_res = client_session.get(f"{BASE_URL}/api/pets")
        pets = pets_res.json()
        
        if len(pets) == 0:
            pet_data = {
                "name": "TEST_Firulais",
                "species": "perro",
                "breed": "Labrador",
                "size": "grande",
                "age": 3,
                "sex": "macho"
            }
            pets_res = client_session.post(f"{BASE_URL}/api/pets", json=pet_data)
            pet_id = pets_res.json().get('pet_id')
        else:
            pet_id = pets[0].get('pet_id')
        
        care_request_data = {
            "pet_id": pet_id,
            "service_type": "cuidado",
            "description": "TEST_Necesito cuidado de fin de semana para mi mascota.",
            "preferred_dates": ["2026-03-15", "2026-03-16"],
            "comuna": "Las Condes",
            "flexible_dates": True
        }
        
        res = client_session.post(f"{BASE_URL}/api/care-requests", json=care_request_data)
        assert res.status_code in [200, 201], f"Failed to create care request: {res.text}"
        return res.json()['request_id']
    
    def test_free_provider_cannot_create_proposal(self, free_provider_session, care_request_id):
        """Test POST /api/proposals - free provider should get 403"""
        proposal_data = {
            "care_request_id": care_request_id,
            "price": 15000,
            "message": "Me encantaria cuidar a tu mascota!",
            "available_dates": []
        }
        
        res = free_provider_session.post(f"{BASE_URL}/api/proposals", json=proposal_data)
        assert res.status_code == 403, f"Expected 403 for free provider, got {res.status_code}: {res.text}"
        
        data = res.json()
        assert "detail" in data
        assert "suscripcion" in data["detail"].lower() or "premium" in data["detail"].lower()
        print(f"✓ Free provider correctly blocked: {data['detail']}")
    
    def test_client_cannot_create_proposal(self, client_session, care_request_id):
        """Test POST /api/proposals - client (non-provider) should get 403"""
        proposal_data = {
            "care_request_id": care_request_id,
            "price": 15000,
            "message": "Test proposal from client",
            "available_dates": []
        }
        
        res = client_session.post(f"{BASE_URL}/api/proposals", json=proposal_data)
        assert res.status_code == 403, f"Expected 403 for client, got {res.status_code}: {res.text}"
        print(f"✓ Client correctly blocked from creating proposal")


class TestProposalGetEndpoints:
    """Test proposal get endpoints"""
    
    @pytest.fixture(scope="class")
    def client_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    @pytest.fixture(scope="class")
    def free_provider_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": FREE_PROVIDER_EMAIL,
            "password": FREE_PROVIDER_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    def test_get_my_sent_proposals(self, free_provider_session):
        """Test GET /api/proposals/my-sent"""
        res = free_provider_session.get(f"{BASE_URL}/api/proposals/my-sent")
        assert res.status_code == 200
        
        proposals = res.json()
        assert isinstance(proposals, list)
        print(f"✓ Provider has {len(proposals)} sent proposal(s)")
    
    def test_get_received_proposals(self, client_session):
        """Test GET /api/proposals/received"""
        res = client_session.get(f"{BASE_URL}/api/proposals/received")
        assert res.status_code == 200
        
        proposals = res.json()
        assert isinstance(proposals, list)
        print(f"✓ Client has {len(proposals)} received proposal(s)")
    
    def test_get_proposals_for_request(self, client_session):
        """Test GET /api/proposals/for-request/{request_id}"""
        # First get client's requests
        req_res = client_session.get(f"{BASE_URL}/api/care-requests/my-requests")
        requests_list = req_res.json()
        
        if len(requests_list) == 0:
            pytest.skip("No care requests to test proposals for")
        
        request_id = requests_list[0]['request_id']
        res = client_session.get(f"{BASE_URL}/api/proposals/for-request/{request_id}")
        assert res.status_code == 200
        
        proposals = res.json()
        assert isinstance(proposals, list)
        print(f"✓ Care request {request_id} has {len(proposals)} proposal(s)")


class TestProposalResponse:
    """Test accepting/rejecting proposals"""
    
    @pytest.fixture(scope="class")
    def client_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    @pytest.fixture(scope="class")
    def free_provider_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": FREE_PROVIDER_EMAIL,
            "password": FREE_PROVIDER_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    def test_invalid_response_status(self, client_session):
        """Test PUT /api/proposals/{id}/respond with invalid status"""
        # Create a fake proposal_id - endpoint should validate before checking if proposal exists
        res = client_session.put(f"{BASE_URL}/api/proposals/fake_prop_id/respond", json={
            "status": "invalid_status"
        })
        # Should get 400 for invalid status or 404 for not found
        assert res.status_code in [400, 404], f"Expected 400 or 404, got {res.status_code}"
        print(f"✓ Invalid status correctly handled: {res.status_code}")
    
    def test_proposal_not_found(self, client_session):
        """Test PUT /api/proposals/{id}/respond with non-existent proposal"""
        res = client_session.put(f"{BASE_URL}/api/proposals/prop_nonexistent123/respond", json={
            "status": "accepted"
        })
        assert res.status_code in [400, 404], f"Expected 400 or 404, got {res.status_code}"
        print(f"✓ Non-existent proposal correctly handled: {res.status_code}")


class TestSubscribedProviderWorkflow:
    """Test workflow with a subscribed provider - requires creating subscription"""
    
    @pytest.fixture(scope="class")
    def admin_session(self):
        session = requests.Session()
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = res.json()
        session.headers.update({"Authorization": f"Bearer {data['token']}"})
        return session
    
    def test_check_provider_subscription_status(self, admin_session):
        """Check provider subscription status via admin"""
        # Get users list to find provider
        res = admin_session.get(f"{BASE_URL}/api/admin/users")
        
        if res.status_code != 200:
            pytest.skip("Cannot access admin users endpoint")
        
        users = res.json()
        provider = next((u for u in users if u.get('email') == FREE_PROVIDER_EMAIL), None)
        
        if provider:
            print(f"Provider {FREE_PROVIDER_EMAIL} found in users")
            print(f"  User ID: {provider.get('user_id')}")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
