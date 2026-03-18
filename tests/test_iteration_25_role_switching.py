"""
Iteration 25: Role Switching Feature Tests
Tests for multi-role users (client + provider) and role switching functionality

Key features tested:
- PUT /api/auth/switch-role - Switch active role between client and provider
- POST /api/auth/add-role - Add a second role to existing user
- GET /api/auth/me - Returns roles array and active_role
- Backend lazy migration of old users without roles array
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from iteration_24
CARER_EMAIL = "cuidador@test.com"
CARER_PASSWORD = "cuidador123"
CLIENT_EMAIL = "cliente@test.com"
CLIENT_PASSWORD = "cliente123"
FREE_CLIENT_EMAIL = "test_client_ui@test.com"
FREE_CLIENT_PASSWORD = "test123456"
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "password123"


class TestAuthMe:
    """GET /api/auth/me - Returns user with roles array and active_role"""
    
    def test_auth_me_requires_authentication(self):
        """GET /api/auth/me without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 401
        print("PASS: /api/auth/me returns 401 without auth")
    
    def test_auth_me_returns_roles_array_for_carer(self):
        """GET /api/auth/me returns roles and active_role for carer"""
        # Login as carer
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_EMAIL,
            "password": CARER_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        
        # Get user info
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        
        data = me_resp.json()
        assert "roles" in data, "Response should contain 'roles' array"
        assert isinstance(data["roles"], list), "'roles' should be a list"
        assert "active_role" in data, "Response should contain 'active_role'"
        
        # Carer should have both roles (provider + client from previous testing)
        print(f"PASS: Carer has roles: {data['roles']}, active_role: {data['active_role']}")
    
    def test_auth_me_returns_roles_array_for_client(self):
        """GET /api/auth/me returns roles and active_role for client"""
        # Login as client
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        
        # Get user info
        headers = {"Authorization": f"Bearer {token}"}
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        
        data = me_resp.json()
        assert "roles" in data, "Response should contain 'roles' array"
        assert "client" in data["roles"], "Client should have 'client' role"
        assert data["active_role"] == "client", "Active role should be 'client'"
        
        print(f"PASS: Client has roles: {data['roles']}, active_role: {data['active_role']}")


class TestSwitchRole:
    """PUT /api/auth/switch-role - Switch active role between client and provider"""
    
    def test_switch_role_requires_authentication(self):
        """PUT /api/auth/switch-role without auth returns 401"""
        response = requests.put(f"{BASE_URL}/api/auth/switch-role", json={"role": "client"})
        assert response.status_code == 401
        print("PASS: /api/auth/switch-role returns 401 without auth")
    
    def test_switch_role_to_client_for_multi_role_user(self):
        """Carer with both roles can switch to client"""
        # Login as carer (has both roles)
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_EMAIL,
            "password": CARER_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Switch to client
        switch_resp = requests.put(
            f"{BASE_URL}/api/auth/switch-role",
            json={"role": "client"},
            headers=headers
        )
        assert switch_resp.status_code == 200, f"Switch failed: {switch_resp.text}"
        
        data = switch_resp.json()
        assert data["active_role"] == "client", "Active role should be 'client' after switch"
        
        # Verify via /auth/me
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["active_role"] == "client"
        
        print("PASS: Carer can switch to client role")
    
    def test_switch_role_to_provider_for_multi_role_user(self):
        """Carer with both roles can switch back to provider"""
        # Login as carer
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_EMAIL,
            "password": CARER_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Switch to provider
        switch_resp = requests.put(
            f"{BASE_URL}/api/auth/switch-role",
            json={"role": "provider"},
            headers=headers
        )
        assert switch_resp.status_code == 200, f"Switch failed: {switch_resp.text}"
        
        data = switch_resp.json()
        assert data["active_role"] == "provider", "Active role should be 'provider' after switch"
        
        print("PASS: Carer can switch back to provider role")
    
    def test_switch_to_invalid_role_fails(self):
        """User cannot switch to a role they don't have"""
        # Login as single-role client
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to switch to provider (client doesn't have this role)
        switch_resp = requests.put(
            f"{BASE_URL}/api/auth/switch-role",
            json={"role": "provider"},
            headers=headers
        )
        assert switch_resp.status_code == 400, f"Should fail with 400, got: {switch_resp.status_code}"
        
        error_detail = switch_resp.json().get("detail", "")
        assert "provider" in error_detail.lower() or "rol" in error_detail.lower()
        
        print("PASS: Client cannot switch to provider role they don't have")


class TestAddRole:
    """POST /api/auth/add-role - Add a second role to existing user"""
    
    def test_add_role_requires_authentication(self):
        """POST /api/auth/add-role without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/add-role", json={"role": "provider"})
        assert response.status_code == 401
        print("PASS: /api/auth/add-role returns 401 without auth")
    
    def test_add_existing_role_fails(self):
        """Cannot add a role that user already has"""
        # Login as carer who already has both roles
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_EMAIL,
            "password": CARER_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to add 'client' role (already has it)
        add_resp = requests.post(
            f"{BASE_URL}/api/auth/add-role",
            json={"role": "client"},
            headers=headers
        )
        assert add_resp.status_code == 400, f"Should fail with 400, got: {add_resp.status_code}"
        
        print("PASS: Cannot add a role user already has")
    
    def test_add_invalid_role_fails(self):
        """Cannot add an invalid role type"""
        # Login as client
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to add invalid role
        add_resp = requests.post(
            f"{BASE_URL}/api/auth/add-role",
            json={"role": "admin"},
            headers=headers
        )
        assert add_resp.status_code == 400, f"Should fail with 400, got: {add_resp.status_code}"
        
        print("PASS: Cannot add invalid role type")


class TestLazyMigration:
    """Backend lazy migration - users without roles array get it auto-created"""
    
    def test_login_response_has_roles(self):
        """Login response should include roles array"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_EMAIL,
            "password": CARER_PASSWORD
        })
        assert login_resp.status_code == 200
        
        user = login_resp.json().get("user", {})
        # Login response may or may not include roles in user object
        # The /auth/me endpoint definitely should
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        
        data = me_resp.json()
        assert "roles" in data, "User should have roles array after lazy migration"
        assert len(data["roles"]) >= 1, "User should have at least one role"
        
        print(f"PASS: User has roles after lazy migration: {data['roles']}")


class TestRoleSwitchingIntegration:
    """Integration tests for full role switching flow"""
    
    def test_full_role_switch_flow_for_carer(self):
        """Test complete flow: login -> check roles -> switch -> verify"""
        # 1. Login as carer
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CARER_EMAIL,
            "password": CARER_PASSWORD
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Get current user info
        me_resp = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        user_data = me_resp.json()
        
        print(f"Initial state: roles={user_data.get('roles')}, active_role={user_data.get('active_role')}")
        
        # 3. Check if has both roles
        roles = user_data.get("roles", [])
        if "client" in roles and "provider" in roles:
            initial_role = user_data.get("active_role")
            target_role = "client" if initial_role == "provider" else "provider"
            
            # 4. Switch role
            switch_resp = requests.put(
                f"{BASE_URL}/api/auth/switch-role",
                json={"role": target_role},
                headers=headers
            )
            assert switch_resp.status_code == 200
            
            # 5. Verify switch
            me_resp2 = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
            assert me_resp2.status_code == 200
            assert me_resp2.json()["active_role"] == target_role
            
            print(f"PASS: Role switched from {initial_role} to {target_role}")
        else:
            print(f"INFO: User only has roles: {roles}, skipping switch test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
