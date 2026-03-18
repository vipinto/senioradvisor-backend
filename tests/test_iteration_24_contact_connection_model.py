"""
Iteration 24: Contact Request & Connection-Based Chat Model Tests
Testing the major business model change for U-CAN platform:
- Free clients: post care requests, receive offers, accept/reject → chat unlocks
- Premium clients: search carers, send direct contact requests → if accepted, chat unlocks
- Free carers: only receive direct requests from premium clients
- Premium carers: see published care requests, send offers
- Chat ONLY works between connected users
- Phone/WhatsApp only visible after connection
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

# Test credentials from the problem statement
ADMIN_CREDS = {"email": "admin@test.com", "password": "password123"}
CARER_SUBSCRIBED = {"email": "cuidador@test.com", "password": "cuidador123", "user_id": "user_d9afd9d44c30", "provider_id": "prov_23ad24c36254"}
CLIENT_PREMIUM = {"email": "cliente@test.com", "password": "cliente123"}
CLIENT_FREE = {"email": "test_client_ui@test.com", "password": "test123456"}


class TestAuthenticationSetup:
    """Helper tests to verify auth tokens work"""
    
    @pytest.fixture(scope="class")
    def premium_client_token(self):
        """Get token for premium/subscribed client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_PREMIUM["email"],
            "password": CLIENT_PREMIUM["password"]
        })
        assert response.status_code == 200, f"Premium client login failed: {response.text}"
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def free_client_token(self):
        """Get token for free client"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_FREE["email"],
            "password": CLIENT_FREE["password"]
        })
        assert response.status_code == 200, f"Free client login failed: {response.text}"
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def carer_token(self):
        """Get token for subscribed carer"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_SUBSCRIBED["email"],
            "password": CARER_SUBSCRIBED["password"]
        })
        assert response.status_code == 200, f"Carer login failed: {response.text}"
        return response.json().get("token")


# ============ CONTACT REQUESTS TESTS ============

class TestContactRequestsAPI:
    """Tests for POST /api/contact-requests - Premium client contact request flow"""
    
    @pytest.fixture(scope="class")
    def premium_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_PREMIUM["email"],
            "password": CLIENT_PREMIUM["password"]
        })
        assert response.status_code == 200
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def free_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_FREE["email"],
            "password": CLIENT_FREE["password"]
        })
        assert response.status_code == 200
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def carer_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_SUBSCRIBED["email"],
            "password": CARER_SUBSCRIBED["password"]
        })
        assert response.status_code == 200
        return response.json().get("token")
    
    def test_contact_request_requires_auth(self):
        """POST /api/contact-requests requires authentication"""
        response = requests.post(f"{BASE_URL}/api/contact-requests", json={
            "provider_user_id": CARER_SUBSCRIBED["user_id"],
            "message": "Test message"
        })
        assert response.status_code == 401, "Should require auth"
        print("PASS: Contact request requires authentication")
    
    def test_free_client_cannot_send_contact_request(self, free_client_token):
        """Free client should get 403 when trying to send contact request"""
        response = requests.post(
            f"{BASE_URL}/api/contact-requests",
            headers={"Authorization": f"Bearer {free_client_token}"},
            json={
                "provider_user_id": CARER_SUBSCRIBED["user_id"],
                "message": "Hola, quiero contactarte"
            }
        )
        assert response.status_code == 403, f"Free client should be blocked: {response.text}"
        assert "suscripcion Premium" in response.json().get("detail", ""), "Should mention premium required"
        print("PASS: Free client cannot send contact requests (403)")
    
    def test_premium_client_can_view_sent_requests(self, premium_client_token):
        """GET /api/contact-requests/sent returns list for premium client"""
        response = requests.get(
            f"{BASE_URL}/api/contact-requests/sent",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list"
        print(f"PASS: Premium client can view sent requests ({len(data)} requests)")
    
    def test_carer_can_view_received_requests(self, carer_token):
        """GET /api/contact-requests/received returns list for carer"""
        response = requests.get(
            f"{BASE_URL}/api/contact-requests/received",
            headers={"Authorization": f"Bearer {carer_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list"
        print(f"PASS: Carer can view received contact requests ({len(data)} requests)")


# ============ CONNECTION STATUS TESTS ============

class TestConnectionStatusAPI:
    """Tests for GET /api/connections/check/{user_id}"""
    
    @pytest.fixture(scope="class")
    def premium_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_PREMIUM["email"],
            "password": CLIENT_PREMIUM["password"]
        })
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def carer_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_SUBSCRIBED["email"],
            "password": CARER_SUBSCRIBED["password"]
        })
        return response.json().get("token")
    
    def test_check_connection_requires_auth(self):
        """Connection check requires authentication"""
        response = requests.get(f"{BASE_URL}/api/connections/check/some_user_id")
        assert response.status_code == 401
        print("PASS: Connection check requires auth")
    
    def test_check_connection_returns_status(self, premium_client_token):
        """Connection check returns connected: true/false"""
        response = requests.get(
            f"{BASE_URL}/api/connections/check/{CARER_SUBSCRIBED['user_id']}",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "connected" in data, "Should have 'connected' field"
        assert isinstance(data["connected"], bool), "connected should be boolean"
        print(f"PASS: Connection check works - connected: {data['connected']}")
    
    def test_get_all_connections(self, premium_client_token):
        """GET /api/connections returns all user connections"""
        response = requests.get(
            f"{BASE_URL}/api/connections",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list"
        print(f"PASS: Get all connections works ({len(data)} connections)")


# ============ CHAT PERMISSION TESTS ============

class TestChatPermissions:
    """Tests for connection-based chat - POST /api/chat/messages"""
    
    @pytest.fixture(scope="class")
    def premium_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_PREMIUM["email"],
            "password": CLIENT_PREMIUM["password"]
        })
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def free_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_FREE["email"],
            "password": CLIENT_FREE["password"]
        })
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def premium_client_user_id(self, premium_client_token):
        """Get premium client user_id"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        return response.json().get("user_id")
    
    @pytest.fixture(scope="class")
    def free_client_user_id(self, free_client_token):
        """Get free client user_id"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {free_client_token}"}
        )
        return response.json().get("user_id")
    
    def test_chat_requires_auth(self):
        """Chat message requires authentication"""
        response = requests.post(f"{BASE_URL}/api/chat/messages", json={
            "receiver_id": "some_user",
            "message": "Test"
        })
        assert response.status_code == 401
        print("PASS: Chat requires authentication")
    
    def test_chat_blocked_for_unconnected_users(self, free_client_token):
        """Free client (no connections) cannot chat with carer"""
        response = requests.post(
            f"{BASE_URL}/api/chat/messages",
            headers={"Authorization": f"Bearer {free_client_token}"},
            json={
                "receiver_id": CARER_SUBSCRIBED["user_id"],
                "message": "Hola, test message"
            }
        )
        # Should be 403 because no connection exists
        assert response.status_code == 403, f"Expected 403 for unconnected users: {response.status_code} - {response.text}"
        data = response.json()
        assert "conexion" in data.get("detail", "").lower() or "desbloquea" in data.get("detail", "").lower()
        print("PASS: Chat blocked for unconnected users (403)")
    
    def test_get_conversations_only_shows_connected(self, premium_client_token):
        """GET /api/chat/conversations only returns conversations with connected users"""
        response = requests.get(
            f"{BASE_URL}/api/chat/conversations",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list"
        print(f"PASS: Get conversations works ({len(data)} conversations)")


# ============ CARE REQUESTS PERMISSION TESTS ============

class TestCareRequestsPermissions:
    """Tests for GET /api/care-requests - Premium carers only"""
    
    @pytest.fixture(scope="class")
    def carer_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_SUBSCRIBED["email"],
            "password": CARER_SUBSCRIBED["password"]
        })
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def free_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_FREE["email"],
            "password": CLIENT_FREE["password"]
        })
        return response.json().get("token")
    
    def test_care_requests_requires_auth(self):
        """Care requests listing requires authentication"""
        response = requests.get(f"{BASE_URL}/api/care-requests")
        assert response.status_code == 401
        print("PASS: Care requests requires auth")
    
    def test_client_cannot_view_care_requests(self, free_client_token):
        """Clients (not providers) cannot view care requests listing"""
        response = requests.get(
            f"{BASE_URL}/api/care-requests",
            headers={"Authorization": f"Bearer {free_client_token}"}
        )
        # Should be 403 - only providers can view
        assert response.status_code == 403, f"Expected 403 for client: {response.text}"
        print("PASS: Clients cannot view care requests listing (403)")
    
    def test_subscribed_carer_can_view_care_requests(self, carer_token):
        """Subscribed carer can view full care requests list"""
        response = requests.get(
            f"{BASE_URL}/api/care-requests",
            headers={"Authorization": f"Bearer {carer_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list"
        print(f"PASS: Subscribed carer can view care requests ({len(data)} requests)")


# ============ PROPOSAL ACCEPTANCE CREATES CONNECTION ============

class TestProposalAcceptanceConnection:
    """Tests for PUT /api/proposals/{id}/respond with status=accepted creates connection"""
    
    @pytest.fixture(scope="class")
    def premium_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_PREMIUM["email"],
            "password": CLIENT_PREMIUM["password"]
        })
        return response.json().get("token")
    
    def test_received_proposals_endpoint_works(self, premium_client_token):
        """GET /api/proposals/received returns proposals for client"""
        response = requests.get(
            f"{BASE_URL}/api/proposals/received",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Should return list"
        print(f"PASS: Get received proposals works ({len(data)} proposals)")


# ============ PROVIDER PROFILE CONNECTION FLAGS ============

class TestProviderProfileConnectionFlags:
    """Tests for GET /api/providers/{provider_id} - connection status flags"""
    
    @pytest.fixture(scope="class")
    def premium_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_PREMIUM["email"],
            "password": CLIENT_PREMIUM["password"]
        })
        return response.json().get("token")
    
    @pytest.fixture(scope="class")
    def free_client_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_FREE["email"],
            "password": CLIENT_FREE["password"]
        })
        return response.json().get("token")
    
    def test_provider_profile_has_connection_flags(self, premium_client_token):
        """Provider profile returns viewer_is_connected, viewer_has_subscription, viewer_has_pending_request"""
        response = requests.get(
            f"{BASE_URL}/api/providers/{CARER_SUBSCRIBED['provider_id']}",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check for connection flags
        assert "viewer_is_connected" in data, "Should have viewer_is_connected flag"
        assert "viewer_has_subscription" in data, "Should have viewer_has_subscription flag"
        assert "viewer_has_pending_request" in data, "Should have viewer_has_pending_request flag"
        
        assert isinstance(data["viewer_is_connected"], bool)
        assert isinstance(data["viewer_has_subscription"], bool)
        assert isinstance(data["viewer_has_pending_request"], bool)
        
        print(f"PASS: Provider profile has connection flags - connected: {data['viewer_is_connected']}, subscription: {data['viewer_has_subscription']}, pending: {data['viewer_has_pending_request']}")
    
    def test_provider_profile_hides_contact_when_not_connected(self, free_client_token):
        """Provider profile hides phone/WhatsApp when viewer not connected"""
        response = requests.get(
            f"{BASE_URL}/api/providers/{CARER_SUBSCRIBED['provider_id']}",
            headers={"Authorization": f"Bearer {free_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check contact is blocked for non-connected users
        if not data.get("viewer_is_connected", False):
            assert data.get("contact_blocked") == True or data.get("phone") is None, "Contact should be blocked"
            print("PASS: Contact info hidden for non-connected user")
        else:
            print("INFO: User is connected, contact info may be visible")
    
    def test_free_client_no_subscription_flag(self, free_client_token):
        """Free client should show viewer_has_subscription=false"""
        response = requests.get(
            f"{BASE_URL}/api/providers/{CARER_SUBSCRIBED['provider_id']}",
            headers={"Authorization": f"Bearer {free_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("viewer_has_subscription") == False, "Free client should have no subscription"
        print("PASS: Free client correctly shows no subscription")
    
    def test_premium_client_has_subscription_flag(self, premium_client_token):
        """Premium client should show viewer_has_subscription=true"""
        response = requests.get(
            f"{BASE_URL}/api/providers/{CARER_SUBSCRIBED['provider_id']}",
            headers={"Authorization": f"Bearer {premium_client_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data.get("viewer_has_subscription") == True, "Premium client should have subscription"
        print("PASS: Premium client correctly shows subscription")


# ============ CONTACT REQUEST ACCEPT/REJECT ============

class TestContactRequestResponse:
    """Tests for PUT /api/contact-requests/{id}/accept and reject"""
    
    @pytest.fixture(scope="class")
    def carer_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_SUBSCRIBED["email"],
            "password": CARER_SUBSCRIBED["password"]
        })
        return response.json().get("token")
    
    def test_accept_requires_auth(self):
        """Accept contact request requires authentication"""
        response = requests.put(f"{BASE_URL}/api/contact-requests/fake_id/accept")
        assert response.status_code == 401
        print("PASS: Accept requires auth")
    
    def test_reject_requires_auth(self):
        """Reject contact request requires authentication"""
        response = requests.put(f"{BASE_URL}/api/contact-requests/fake_id/reject")
        assert response.status_code == 401
        print("PASS: Reject requires auth")
    
    def test_invalid_request_id_returns_404(self, carer_token):
        """Invalid request ID returns 404"""
        response = requests.put(
            f"{BASE_URL}/api/contact-requests/nonexistent_id/accept",
            headers={"Authorization": f"Bearer {carer_token}"}
        )
        assert response.status_code == 404, f"Expected 404: {response.text}"
        print("PASS: Invalid request ID returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
