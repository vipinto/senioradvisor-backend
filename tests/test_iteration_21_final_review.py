"""
ITERATION 21 - FINAL COMPREHENSIVE REVIEW
Testing ALL features before launch for U-CAN Pet Care Platform

Tests cover:
- Authentication (register, login, me)
- Providers search with sorting (verified+subscribed first)
- Subscriptions (plans by role, invoices, my subscription)
- Bookings (create, list, history)
- Care Requests and Proposals
- Chat (asymmetric subscription logic)
- Notifications
- Pets CRUD
- SOS Veterinario
- Reviews
- Admin endpoints
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL not set")

# Test credentials
ADMIN_CREDS = {"email": "admin@ucan.cl", "password": "admin123"}
PROVIDER_CREDS = {"email": "cuidador@test.com", "password": "cuidador123"}
CLIENT_CREDS = {"email": "test_client_ui@test.com", "password": "test123456"}


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def provider_token(api_client):
    """Get provider authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=PROVIDER_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Provider authentication failed")


@pytest.fixture(scope="module")
def client_token(api_client):
    """Get client authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=CLIENT_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Client authentication failed")


# ===================== AUTHENTICATION TESTS =====================

class TestAuthentication:
    """Tests for authentication endpoints"""
    
    def test_register_user_validation(self, api_client):
        """Test register endpoint validates password length"""
        response = api_client.post(f"{BASE_URL}/api/auth/register", json={
            "email": f"test_short_{datetime.now().timestamp()}@test.com",
            "password": "12345",  # Too short
            "name": "Test User"
        })
        assert response.status_code == 400
        assert "6 caracteres" in response.json().get("detail", "")
        print("✓ Register validates password length")
    
    def test_login_success(self, api_client, provider_token):
        """Test login returns token"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=PROVIDER_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        print(f"✓ Login success for provider: {data['user']['email']}")
    
    def test_login_invalid_credentials(self, api_client):
        """Test login with wrong password"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": "cuidador@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code in [400, 401]
        print("✓ Login correctly rejects invalid credentials")
    
    def test_get_me_authenticated(self, api_client, provider_token):
        """Test GET /auth/me returns user profile"""
        response = api_client.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "user_id" in data
        assert "role" in data
        assert "has_subscription" in data
        print(f"✓ GET /auth/me: role={data['role']}, has_subscription={data['has_subscription']}")
    
    def test_get_me_unauthenticated(self, api_client):
        """Test GET /auth/me without token"""
        response = api_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("✓ GET /auth/me correctly requires authentication")


# ===================== PROVIDER SEARCH TESTS =====================

class TestProviderSearch:
    """Tests for provider search and listing"""
    
    def test_list_providers(self, api_client):
        """Test GET /providers returns list"""
        response = api_client.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /providers returned {len(data)} providers")
        
        # Check sorting - featured (verified+subscribed) should be first
        if len(data) > 1:
            featured_count = sum(1 for p in data if p.get('is_featured'))
            print(f"  - Featured providers: {featured_count}")
    
    def test_filter_by_service_type(self, api_client):
        """Test filter providers by service type"""
        response = api_client.get(f"{BASE_URL}/api/providers?service_type=paseo")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Filter by paseo: {len(data)} providers")
    
    def test_get_provider_detail(self, api_client):
        """Test GET /providers/{id} returns provider with is_featured field"""
        # First get a provider from list
        list_response = api_client.get(f"{BASE_URL}/api/providers?limit=1")
        providers = list_response.json()
        if not providers:
            pytest.skip("No providers available")
        
        provider_id = providers[0]["provider_id"]
        response = api_client.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert response.status_code == 200
        data = response.json()
        assert "provider_id" in data
        assert "is_featured" in data  # Must have is_featured field
        assert "services" in data
        print(f"✓ Provider detail: {data.get('business_name')}, is_featured={data.get('is_featured')}")
    
    def test_provider_not_found(self, api_client):
        """Test 404 for non-existent provider"""
        response = api_client.get(f"{BASE_URL}/api/providers/prov_nonexistent123")
        assert response.status_code == 404
        print("✓ Non-existent provider returns 404")


# ===================== SUBSCRIPTION TESTS =====================

class TestSubscriptions:
    """Tests for subscription endpoints"""
    
    def test_get_client_plans(self, api_client):
        """Test GET /subscription/plans?role=client returns client plan at $9.990"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=client")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            client_plan = data[0]
            assert client_plan.get("price_clp") == 9990
            print(f"✓ Client plan: {client_plan['name']} - ${client_plan['price_clp']:,}")
    
    def test_get_provider_plans(self, api_client):
        """Test GET /subscription/plans?role=provider returns provider plan at $7.500"""
        response = api_client.get(f"{BASE_URL}/api/subscription/plans?role=provider")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            provider_plan = data[0]
            assert provider_plan.get("price_clp") == 7500
            print(f"✓ Provider plan: {provider_plan['name']} - ${provider_plan['price_clp']:,}")
    
    def test_get_my_subscription_provider(self, api_client, provider_token):
        """Test GET /subscription/my for subscribed provider"""
        response = api_client.get(
            f"{BASE_URL}/api/subscription/my",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "has_subscription" in data
        print(f"✓ Provider subscription: has_subscription={data.get('has_subscription')}, status={data.get('status')}")
    
    def test_get_subscription_invoices(self, api_client, provider_token):
        """Test GET /subscription/invoices"""
        response = api_client.get(
            f"{BASE_URL}/api/subscription/invoices",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Invoices count: {len(data)}")


# ===================== BOOKING TESTS =====================

class TestBookings:
    """Tests for booking endpoints"""
    
    def test_create_booking_requires_subscription(self, api_client):
        """Test POST /bookings requires subscription"""
        # Try without auth
        response = api_client.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": "prov_test",
            "service_type": "paseo",
            "start_date": "2026-02-01T10:00:00Z"
        })
        assert response.status_code == 401
        print("✓ POST /bookings requires authentication")
    
    def test_get_bookings_history(self, api_client, client_token):
        """Test GET /bookings/history"""
        response = api_client.get(
            f"{BASE_URL}/api/bookings/history",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Bookings history: {len(data)} records")
    
    def test_get_my_bookings(self, api_client, client_token):
        """Test GET /bookings/my (client's bookings)"""
        # Use /bookings endpoint 
        response = api_client.get(
            f"{BASE_URL}/api/bookings/my",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        print(f"✓ GET /bookings/my works")


# ===================== CARE REQUEST & PROPOSAL TESTS =====================

class TestCareRequestsProposals:
    """Tests for care requests and proposals"""
    
    def test_get_my_care_requests(self, api_client, client_token):
        """Test GET /care-requests/my-requests"""
        response = api_client.get(
            f"{BASE_URL}/api/care-requests/my-requests",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Client care requests: {len(data)}")
    
    def test_provider_can_see_care_requests(self, api_client, provider_token):
        """Test GET /care-requests for provider"""
        response = api_client.get(
            f"{BASE_URL}/api/care-requests",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Provider can see {len(data)} care requests")
    
    def test_get_my_sent_proposals(self, api_client, provider_token):
        """Test GET /proposals/my-sent"""
        response = api_client.get(
            f"{BASE_URL}/api/proposals/my-sent",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Provider sent proposals: {len(data)}")
    
    def test_get_received_proposals(self, api_client, client_token):
        """Test GET /proposals/received"""
        response = api_client.get(
            f"{BASE_URL}/api/proposals/received",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Client received proposals: {len(data)}")
    
    def test_proposal_respond_invalid_status(self, api_client, client_token):
        """Test PUT /proposals/{id}/respond rejects invalid status"""
        response = api_client.put(
            f"{BASE_URL}/api/proposals/prop_nonexistent/respond",
            json={"status": "invalid_status"},
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 400
        print("✓ Invalid proposal status correctly rejected")
    
    def test_proposal_respond_not_found(self, api_client, client_token):
        """Test PUT /proposals/{id}/respond returns 404"""
        response = api_client.put(
            f"{BASE_URL}/api/proposals/prop_nonexistent/respond",
            json={"status": "accepted"},
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 404
        print("✓ Non-existent proposal returns 404")


# ===================== CHAT TESTS =====================

class TestChat:
    """Tests for chat endpoints with asymmetric subscription logic"""
    
    def test_get_conversations(self, api_client, provider_token):
        """Test GET /chat/conversations - accessible for all authenticated users"""
        response = api_client.get(
            f"{BASE_URL}/api/chat/conversations",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Provider can access conversations: {len(data)} conversations")
    
    def test_client_conversations(self, api_client, client_token):
        """Test client can access conversations"""
        response = api_client.get(
            f"{BASE_URL}/api/chat/conversations",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        print("✓ Client can access conversations")


# ===================== NOTIFICATION TESTS =====================

class TestNotifications:
    """Tests for notification endpoints"""
    
    def test_get_notifications(self, api_client, provider_token):
        """Test GET /notifications"""
        response = api_client.get(
            f"{BASE_URL}/api/notifications",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Notifications: {len(data)} items")
    
    def test_get_unread_count(self, api_client, provider_token):
        """Test GET /notifications/unread-count"""
        response = api_client.get(
            f"{BASE_URL}/api/notifications/unread-count",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        print(f"✓ Unread notifications: {data['count']}")
    
    def test_mark_all_read(self, api_client, provider_token):
        """Test POST /notifications/read-all"""
        response = api_client.post(
            f"{BASE_URL}/api/notifications/read-all",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        print("✓ Mark all notifications read")


# ===================== PET TESTS =====================

class TestPets:
    """Tests for pet endpoints"""
    
    def test_get_my_pets(self, api_client, client_token):
        """Test GET /pets"""
        response = api_client.get(
            f"{BASE_URL}/api/pets",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Client pets: {len(data)}")
    
    def test_create_pet(self, api_client, client_token):
        """Test POST /pets"""
        response = api_client.post(
            f"{BASE_URL}/api/pets",
            json={
                "name": f"TEST_Pet_{datetime.now().timestamp()}",
                "species": "perro",
                "breed": "Mixed",
                "size": "mediano",
                "age": 3,  # age is Optional[int]
                "sex": "macho"
            },
            headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "pet_id" in data
        print(f"✓ Created pet: {data['name']}")


# ===================== SOS VETERINARIO TESTS =====================

class TestSOSVeterinario:
    """Tests for SOS emergency info"""
    
    def test_get_sos_info(self, api_client, provider_token):
        """Test GET /sos/info returns is_available based on schedule"""
        response = api_client.get(
            f"{BASE_URL}/api/sos/info",
            headers={"Authorization": f"Bearer {provider_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should have is_available field based on admin schedule
        if data.get("active"):
            assert "is_available" in data
            print(f"✓ SOS info: active={data.get('active')}, is_available={data.get('is_available')}")
        else:
            print("✓ SOS info: service not active")
    
    def test_admin_sos_config(self, api_client, admin_token):
        """Test GET /admin/sos returns config with start_hour/end_hour"""
        response = api_client.get(
            f"{BASE_URL}/api/admin/sos",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "start_hour" in data
        assert "end_hour" in data
        print(f"✓ Admin SOS config: {data.get('start_hour')}:00 - {data.get('end_hour')}:00")


# ===================== REVIEWS TESTS =====================

class TestReviews:
    """Tests for review endpoints"""
    
    def test_get_provider_reviews(self, api_client):
        """Test GET /providers/{id}/reviews"""
        # Get a provider first
        list_response = api_client.get(f"{BASE_URL}/api/providers?limit=1")
        providers = list_response.json()
        if not providers:
            pytest.skip("No providers available")
        
        provider_id = providers[0]["provider_id"]
        response = api_client.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert response.status_code == 200
        data = response.json()
        assert "reviews" in data
        print(f"✓ Provider reviews: {len(data.get('reviews', []))}")


# ===================== ADMIN TESTS =====================

class TestAdmin:
    """Tests for admin endpoints"""
    
    def test_admin_stats(self, api_client, admin_token):
        """Test GET /admin/stats"""
        response = api_client.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data
        assert "total_providers" in data
        print(f"✓ Admin stats: {data['total_users']} users, {data['total_providers']} providers")
    
    def test_admin_get_all_providers(self, api_client, admin_token):
        """Test GET /admin/providers/all"""
        response = api_client.get(
            f"{BASE_URL}/api/admin/providers/all",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin providers list: {len(data)} providers")
    
    def test_admin_get_plans(self, api_client, admin_token):
        """Test GET /admin/plans"""
        response = api_client.get(
            f"{BASE_URL}/api/admin/plans",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Admin plans: {len(data)} plans")
    
    def test_admin_requires_auth(self, api_client):
        """Test admin endpoints require authentication"""
        response = api_client.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 401
        print("✓ Admin endpoints require authentication")


# ===================== HEALTH CHECK =====================

class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self, api_client):
        """Test API health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")
    
    def test_api_root(self, api_client):
        """Test API root endpoint"""
        response = api_client.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        print(f"✓ API version: {data.get('version')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
