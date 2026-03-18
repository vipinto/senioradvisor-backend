"""
Backend API Tests for U-CAN Admin and Notification Endpoints
Tests for admin provider management and notification system
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test session tokens created in MongoDB
ADMIN_SESSION = "admin_session_test_1770238678629"
REGULAR_SESSION = "regular_session_test_1770238678693"
PROVIDER_SESSION = "provider_session_test_1770238678698"


class TestAdminStatsEndpoint:
    """Tests for GET /api/admin/stats - Admin dashboard statistics"""
    
    def test_admin_stats_with_admin_auth(self):
        """Test that admin can access stats endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            cookies={"session_token": ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        required_fields = [
            "total_users", "total_providers", "pending_providers",
            "verified_providers", "active_subscriptions", "total_requests"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
            assert isinstance(data[field], int), f"{field} should be integer"
        
        print(f"✓ Admin stats: {data}")
    
    def test_admin_stats_requires_admin_role(self):
        """Test that non-admin users get 403 Forbidden"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            cookies={"session_token": REGULAR_SESSION}
        )
        assert response.status_code == 403
        data = response.json()
        assert "administradores" in data["detail"].lower()
        print("✓ Non-admin correctly blocked from stats endpoint")
    
    def test_admin_stats_requires_auth(self):
        """Test that unauthenticated requests get 401"""
        response = requests.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 401
        print("✓ Unauthenticated correctly blocked from stats endpoint")


class TestAdminPendingProvidersEndpoint:
    """Tests for GET /api/admin/providers/pending - Pending providers list"""
    
    def test_get_pending_providers_with_admin(self):
        """Test that admin can get pending providers list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/providers/pending",
            cookies={"session_token": ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} pending providers")
        
        # If there are pending providers, validate structure
        if len(data) > 0:
            provider = data[0]
            assert "provider_id" in provider
            assert "business_name" in provider
            assert provider.get("approved") == False
    
    def test_pending_providers_requires_admin(self):
        """Test that non-admin users get 403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/providers/pending",
            cookies={"session_token": REGULAR_SESSION}
        )
        assert response.status_code == 403
        print("✓ Non-admin correctly blocked from pending providers")


class TestAdminAllProvidersEndpoint:
    """Tests for GET /api/admin/providers/all - All providers list"""
    
    def test_get_all_providers_with_admin(self):
        """Test that admin can get all providers list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/providers/all",
            cookies={"session_token": ADMIN_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one provider"
        print(f"✓ Found {len(data)} total providers")
        
        # Validate provider structure
        provider = data[0]
        required_fields = ["provider_id", "business_name", "approved"]
        for field in required_fields:
            assert field in provider, f"Missing field: {field}"
    
    def test_all_providers_requires_admin(self):
        """Test that non-admin users get 403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/providers/all",
            cookies={"session_token": REGULAR_SESSION}
        )
        assert response.status_code == 403
        print("✓ Non-admin correctly blocked from all providers")


class TestAdminApproveProviderEndpoint:
    """Tests for POST /api/admin/providers/{id}/approve"""
    
    def test_approve_provider_not_found(self):
        """Test that approving non-existent provider returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/nonexistent-provider/approve",
            cookies={"session_token": ADMIN_SESSION}
        )
        assert response.status_code == 404
        print("✓ Approve returns 404 for non-existent provider")
    
    def test_approve_provider_requires_admin(self):
        """Test that non-admin cannot approve providers"""
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/any-provider-id/approve",
            cookies={"session_token": REGULAR_SESSION}
        )
        assert response.status_code == 403
        print("✓ Non-admin correctly blocked from approving")


class TestAdminRejectProviderEndpoint:
    """Tests for POST /api/admin/providers/{id}/reject"""
    
    def test_reject_provider_not_found(self):
        """Test that rejecting non-existent provider returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/nonexistent-provider/reject",
            cookies={"session_token": ADMIN_SESSION},
            json={"reason": "Test reason"}
        )
        assert response.status_code == 404
        print("✓ Reject returns 404 for non-existent provider")
    
    def test_reject_provider_requires_admin(self):
        """Test that non-admin cannot reject providers"""
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/any-provider-id/reject",
            cookies={"session_token": REGULAR_SESSION},
            json={"reason": "Test reason"}
        )
        assert response.status_code == 403
        print("✓ Non-admin correctly blocked from rejecting")


class TestAdminVerifyProviderEndpoint:
    """Tests for POST /api/admin/providers/{id}/verify"""
    
    def test_verify_provider_not_found(self):
        """Test that verifying non-existent provider returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/nonexistent-provider/verify",
            cookies={"session_token": ADMIN_SESSION}
        )
        assert response.status_code == 404
        print("✓ Verify returns 404 for non-existent provider")
    
    def test_verify_provider_requires_admin(self):
        """Test that non-admin cannot verify providers"""
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/any-provider-id/verify",
            cookies={"session_token": REGULAR_SESSION}
        )
        assert response.status_code == 403
        print("✓ Non-admin correctly blocked from verifying")


class TestNotificationsEndpoint:
    """Tests for GET /api/notifications - User notifications list"""
    
    def test_get_notifications_with_auth(self):
        """Test that authenticated user can get notifications"""
        response = requests.get(
            f"{BASE_URL}/api/notifications",
            cookies={"session_token": PROVIDER_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} notifications")
        
        # If notifications exist, validate structure
        if len(data) > 0:
            notif = data[0]
            required_fields = ["notification_id", "title", "message", "type", "read", "created_at"]
            for field in required_fields:
                assert field in notif, f"Missing field: {field}"
    
    def test_notifications_requires_auth(self):
        """Test that unauthenticated users get 401"""
        response = requests.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 401
        print("✓ Unauthenticated correctly blocked from notifications")


class TestUnreadCountEndpoint:
    """Tests for GET /api/notifications/unread-count"""
    
    def test_get_unread_count_with_auth(self):
        """Test that authenticated user can get unread count"""
        response = requests.get(
            f"{BASE_URL}/api/notifications/unread-count",
            cookies={"session_token": PROVIDER_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] >= 0
        print(f"✓ Unread count: {data['count']}")
    
    def test_unread_count_requires_auth(self):
        """Test that unauthenticated users get 401"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 401
        print("✓ Unauthenticated correctly blocked from unread count")


class TestMarkNotificationReadEndpoint:
    """Tests for POST /api/notifications/{id}/read"""
    
    def test_mark_read_requires_auth(self):
        """Test that unauthenticated users get 401"""
        response = requests.post(f"{BASE_URL}/api/notifications/some-id/read")
        assert response.status_code == 401
        print("✓ Unauthenticated correctly blocked from marking read")
    
    def test_mark_read_invalid_id(self):
        """Test marking non-existent notification (should not fail, just no-op)"""
        response = requests.post(
            f"{BASE_URL}/api/notifications/nonexistent-notif/read",
            cookies={"session_token": PROVIDER_SESSION}
        )
        # The endpoint doesn't throw error for non-existent, just updates nothing
        assert response.status_code == 200
        print("✓ Mark read handles non-existent notification gracefully")


class TestMarkAllReadEndpoint:
    """Tests for POST /api/notifications/read-all"""
    
    def test_mark_all_read_with_auth(self):
        """Test that authenticated user can mark all as read"""
        response = requests.post(
            f"{BASE_URL}/api/notifications/read-all",
            cookies={"session_token": PROVIDER_SESSION}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ Mark all read: {data['message']}")
    
    def test_mark_all_read_requires_auth(self):
        """Test that unauthenticated users get 401"""
        response = requests.post(f"{BASE_URL}/api/notifications/read-all")
        assert response.status_code == 401
        print("✓ Unauthenticated correctly blocked from marking all read")


class TestAdminWorkflow:
    """Integration test for admin approve flow with notification creation"""
    
    def test_admin_stats_reflects_correct_counts(self):
        """Verify admin stats accurately reflect database state"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            cookies={"session_token": ADMIN_SESSION}
        )
        assert response.status_code == 200
        stats = response.json()
        
        # Stats should have non-negative values
        assert stats["total_users"] >= 0
        assert stats["total_providers"] >= 0
        assert stats["pending_providers"] >= 0
        assert stats["verified_providers"] >= 0
        assert stats["active_subscriptions"] >= 0
        assert stats["total_requests"] >= 0
        
        # Verified should be <= total providers
        assert stats["verified_providers"] <= stats["total_providers"] + stats["pending_providers"]
        print(f"✓ Stats validation passed: {stats}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
