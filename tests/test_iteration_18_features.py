"""
Iteration 18 Tests: New features for U-CAN Pet Services Platform
Tests:
1. GET /api/providers - Featured/promoted providers sorting (verified+subscribed first)
2. GET /api/providers/{id} - is_featured field in provider details
3. GET /api/bookings/history - Service history for authenticated users
4. GET /api/subscription/invoices - Billing/invoices for authenticated users
5. GET /api/sos/info - SOS availability with schedule_text and is_available fields
6. PUT /api/admin/sos - Admin SOS config with start_hour and end_hour
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestProvidersFeaturedsort:
    """Test providers sorting - featured (verified+subscribed) providers first"""
    
    def test_providers_list_returns_providers(self):
        """GET /api/providers should return a list of providers"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"GET /api/providers: Got {len(data)} providers")
    
    def test_providers_have_is_featured_field(self):
        """Each provider in list should have is_featured field"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        if len(providers) > 0:
            for provider in providers[:5]:  # Check first 5
                assert 'is_featured' in provider, f"Provider {provider.get('provider_id')} missing is_featured field"
                assert 'is_verified_only' in provider, f"Provider {provider.get('provider_id')} missing is_verified_only field"
                print(f"Provider {provider.get('business_name', 'N/A')}: is_featured={provider.get('is_featured')}, is_verified_only={provider.get('is_verified_only')}, verified={provider.get('verified')}")
        else:
            print("No providers found to test")
    
    def test_providers_sorted_by_featured_status(self):
        """Featured providers (verified+subscribed) should appear first"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        providers = response.json()
        
        if len(providers) < 2:
            print("Not enough providers to test sorting")
            return
        
        # Check sorting order: featured (0) -> verified_only (1) -> rest (2)
        prev_sort_key = -1
        for provider in providers[:10]:  # Check first 10
            if provider.get('is_featured'):
                sort_key = 0
            elif provider.get('is_verified_only'):
                sort_key = 1
            else:
                sort_key = 2
            
            # Sort key should be >= previous (non-decreasing order)
            assert sort_key >= prev_sort_key, f"Sort order violation: provider {provider.get('business_name')} has sort_key {sort_key} but previous was {prev_sort_key}"
            prev_sort_key = sort_key
        
        print("Providers sorting verified: featured -> verified_only -> rest")


class TestProviderDetailsFeatured:
    """Test individual provider details include is_featured"""
    
    def test_provider_details_has_is_featured(self):
        """GET /api/providers/{id} should include is_featured field"""
        # First get a provider ID from the list
        list_response = requests.get(f"{BASE_URL}/api/providers")
        assert list_response.status_code == 200
        providers = list_response.json()
        
        if len(providers) == 0:
            pytest.skip("No providers available to test")
        
        provider_id = providers[0]['provider_id']
        detail_response = requests.get(f"{BASE_URL}/api/providers/{provider_id}")
        assert detail_response.status_code == 200, f"Expected 200, got {detail_response.status_code}"
        
        provider = detail_response.json()
        assert 'is_featured' in provider, "Provider details missing is_featured field"
        print(f"Provider {provider.get('business_name')}: is_featured={provider.get('is_featured')}")


class TestServiceHistory:
    """Test service history endpoint for authenticated users"""
    
    @pytest.fixture
    def provider_token(self):
        """Login as provider and get token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "cuidador@test.com",
            "password": "cuidador123"
        })
        if login_response.status_code != 200:
            pytest.skip("Provider login failed - skipping history tests")
        return login_response.json().get('token')
    
    @pytest.fixture
    def client_token(self):
        """Login as client and get token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test_client_ui@test.com",
            "password": "test123456"
        })
        if login_response.status_code != 200:
            pytest.skip("Client login failed - skipping history tests")
        return login_response.json().get('token')
    
    def test_service_history_requires_auth(self):
        """GET /api/bookings/history should require authentication"""
        response = requests.get(f"{BASE_URL}/api/bookings/history")
        assert response.status_code == 401 or response.status_code == 403, f"Expected 401/403, got {response.status_code}"
        print("Service history correctly requires authentication")
    
    def test_service_history_returns_list(self, provider_token):
        """GET /api/bookings/history returns list of completed/finished bookings"""
        headers = {"Authorization": f"Bearer {provider_token}"}
        response = requests.get(f"{BASE_URL}/api/bookings/history", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Service history: Got {len(data)} entries")
        
        if len(data) > 0:
            booking = data[0]
            # Check expected fields
            assert 'booking_id' in booking or 'status' in booking, "Missing expected booking fields"
            print(f"Sample history entry: status={booking.get('status')}, service={booking.get('service_type')}")


class TestSubscriptionInvoices:
    """Test subscription invoices/billing history endpoint"""
    
    @pytest.fixture
    def user_token(self):
        """Login and get token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "cuidador@test.com",
            "password": "cuidador123"
        })
        if login_response.status_code != 200:
            pytest.skip("Login failed - skipping invoice tests")
        return login_response.json().get('token')
    
    def test_invoices_requires_auth(self):
        """GET /api/subscription/invoices should require authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/invoices")
        assert response.status_code == 401 or response.status_code == 403, f"Expected 401/403, got {response.status_code}"
        print("Invoices endpoint correctly requires authentication")
    
    def test_invoices_returns_list(self, user_token):
        """GET /api/subscription/invoices returns billing history"""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = requests.get(f"{BASE_URL}/api/subscription/invoices", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Invoices: Got {len(data)} entries")
        
        if len(data) > 0:
            invoice = data[0]
            # Check expected fields
            assert 'subscription_id' in invoice, "Invoice missing subscription_id"
            assert 'plan_name' in invoice, "Invoice missing plan_name"
            assert 'amount' in invoice, "Invoice missing amount"
            assert 'status' in invoice, "Invoice missing status"
            print(f"Sample invoice: plan={invoice.get('plan_name')}, amount={invoice.get('amount')}, status={invoice.get('status')}")


class TestSOSInfo:
    """Test SOS info endpoint with schedule availability"""
    
    @pytest.fixture
    def user_token(self):
        """Login and get token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "cuidador@test.com",
            "password": "cuidador123"
        })
        if login_response.status_code != 200:
            pytest.skip("Login failed - skipping SOS tests")
        return login_response.json().get('token')
    
    def test_sos_info_returns_availability_fields(self, user_token):
        """GET /api/sos/info should return is_available and schedule_text"""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = requests.get(f"{BASE_URL}/api/sos/info", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # If SOS is active, check for required fields
        if data.get('active'):
            assert 'is_available' in data, "SOS info missing is_available field"
            assert 'schedule_text' in data, "SOS info missing schedule_text field"
            print(f"SOS info: active={data.get('active')}, is_available={data.get('is_available')}, schedule_text={data.get('schedule_text')}")
            print(f"Current hour (Chile): {data.get('current_hour')}")
        else:
            print("SOS is not active - basic test passed")


class TestAdminSOSConfig:
    """Test admin SOS configuration with start/end hour"""
    
    @pytest.fixture
    def admin_token(self):
        """Login as admin and get token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        if login_response.status_code != 200:
            pytest.skip("Admin login failed - skipping admin SOS tests")
        return login_response.json().get('token')
    
    def test_admin_get_sos_config(self, admin_token):
        """GET /api/admin/sos should return SOS config with hour fields"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/sos", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'start_hour' in data, "SOS config missing start_hour field"
        assert 'end_hour' in data, "SOS config missing end_hour field"
        print(f"Admin SOS config: start_hour={data.get('start_hour')}, end_hour={data.get('end_hour')}, active={data.get('active')}")
    
    def test_admin_update_sos_config_with_hours(self, admin_token):
        """PUT /api/admin/sos should accept start_hour and end_hour"""
        headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
        
        # First get current config
        get_response = requests.get(f"{BASE_URL}/api/admin/sos", headers=headers)
        current_config = get_response.json()
        
        # Update with new hours
        update_data = {
            "active": True,
            "phone": current_config.get('phone', '+56912345678'),
            "vet_name": current_config.get('vet_name', 'Dr. Test'),
            "start_hour": 8,
            "end_hour": 20
        }
        
        response = requests.put(f"{BASE_URL}/api/admin/sos", headers=headers, json=update_data)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        updated = response.json()
        assert updated.get('start_hour') == 8, f"Expected start_hour=8, got {updated.get('start_hour')}"
        assert updated.get('end_hour') == 20, f"Expected end_hour=20, got {updated.get('end_hour')}"
        print(f"Admin SOS update successful: start_hour={updated.get('start_hour')}, end_hour={updated.get('end_hour')}")


class TestAuthEndpoints:
    """Basic auth tests for credential validation"""
    
    def test_provider_login(self):
        """Login as provider (cuidador) should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "cuidador@test.com",
            "password": "cuidador123"
        })
        assert response.status_code == 200, f"Provider login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert 'token' in data, "Login response missing token"
        print(f"Provider login successful: user={data.get('user', {}).get('name', 'N/A')}")
    
    def test_admin_login(self):
        """Login as admin should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@ucan.cl",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Admin login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert 'token' in data, "Login response missing token"
        print(f"Admin login successful: user={data.get('user', {}).get('name', 'N/A')}, role={data.get('user', {}).get('role', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
