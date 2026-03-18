"""
Booking System API Tests (Iteration 16)
Tests for: POST /api/bookings, GET /api/bookings/my, GET /api/bookings/provider,
PUT /api/bookings/{id}/respond, PUT /api/bookings/{id}/cancel, PUT /api/bookings/{id}/complete,
GET /api/bookings/stats/summary

All booking endpoints tested for authentication, authorization, and functionality.
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "ucan")

TEST_PREFIX = "TEST_BOOK16_"

# ============= AUTHENTICATION TESTS =============

def test_create_booking_requires_auth():
    """POST /api/bookings should require authentication"""
    res = requests.post(f"{BASE_URL}/api/bookings", json={
        "provider_id": "test",
        "service_type": "paseo",
        "start_date": datetime.utcnow().isoformat(),
        "pet_ids": []
    })
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("✓ Create booking requires auth (401)")


def test_get_my_bookings_requires_auth():
    """GET /api/bookings/my should require authentication"""
    res = requests.get(f"{BASE_URL}/api/bookings/my")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("✓ Get my bookings requires auth (401)")


def test_get_provider_bookings_requires_auth():
    """GET /api/bookings/provider should require authentication"""
    res = requests.get(f"{BASE_URL}/api/bookings/provider")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("✓ Get provider bookings requires auth (401)")


def test_get_booking_stats_requires_auth():
    """GET /api/bookings/stats/summary should require authentication"""
    res = requests.get(f"{BASE_URL}/api/bookings/stats/summary")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("✓ Get booking stats requires auth (401)")


# ============= FULL BOOKING FLOW TESTS =============

def test_booking_full_flow():
    """Test complete booking flow: create -> confirm -> complete"""
    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    password = "testpass123456"
    unique_id = uuid.uuid4().hex[:6]
    
    try:
        # 1. Create client user (always fresh)
        client_email = f"{TEST_PREFIX}client_{unique_id}@test.com"
        client_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": client_email,
            "password": password,
            "name": f"{TEST_PREFIX}Client",
            "role": "client"
        })
        assert client_res.status_code == 200, f"Client registration failed: {client_res.text}"
        client_token = client_res.json()["token"]
        client_user_id = client_res.json()["user"]["user_id"]
        print(f"  ✓ Client created: {client_user_id}")
        
        # 2. Grant subscription
        db.subscriptions.update_one(
            {"user_id": client_user_id},
            {"$set": {
                "user_id": client_user_id,
                "plan_id": "plan_test",
                "status": "active",
                "start_date": datetime.utcnow(),
                "end_date": datetime.utcnow() + timedelta(days=30)
            }},
            upsert=True
        )
        print("  ✓ Subscription granted")
        
        # 3. Create provider user (always fresh)
        provider_email = f"{TEST_PREFIX}provider_{unique_id}@test.com"
        prov_reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": provider_email,
            "password": password,
            "name": f"{TEST_PREFIX}Provider",
            "role": "client"
        })
        assert prov_reg_res.status_code == 200, f"Provider registration failed: {prov_reg_res.text}"
        provider_token = prov_reg_res.json()["token"]
        provider_user_id = prov_reg_res.json()["user"]["user_id"]
        
        # Create provider profile
        prov_res = requests.post(f"{BASE_URL}/api/providers", json={
            "business_name": f"{TEST_PREFIX}Carer",
            "description": "Test provider",
            "address": "Test Address",
            "comuna": "Santiago",
            "phone": "+56912345678",
            "services_offered": [
                {"service_type": "paseo", "price_from": 15000, "pet_sizes": ["pequeno", "mediano", "grande"]}
            ]
        }, headers={"Authorization": f"Bearer {provider_token}"})
        assert prov_res.status_code in [200, 201], f"Provider profile failed: {prov_res.text}"
        provider_id = prov_res.json()["provider_id"]
        print(f"  ✓ Provider created: {provider_id}")
        
        # 4. Create pet
        pet_res = requests.post(f"{BASE_URL}/api/pets", json={
            "name": f"{TEST_PREFIX}Dog",
            "species": "perro",
            "size": "mediano",
            "sex": "macho"
        }, headers={"Authorization": f"Bearer {client_token}"})
        assert pet_res.status_code in [200, 201], f"Pet creation failed: {pet_res.text}"
        pet_id = pet_res.json()["pet_id"]
        print(f"  ✓ Pet created: {pet_id}")
        
        # 5. Test booking without subscription fails
        nosub_email = f"{TEST_PREFIX}nosub_{unique_id}@test.com"
        nosub_reg = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": nosub_email,
            "password": password,
            "name": "NoSub User",
            "role": "client"
        })
        if nosub_reg.status_code == 200:
            nosub_token = nosub_reg.json()["token"]
            # Create a pet for nosub user
            nosub_pet_res = requests.post(f"{BASE_URL}/api/pets", json={
                "name": "NoSubPet",
                "species": "perro",
                "size": "mediano",
                "sex": "macho"
            }, headers={"Authorization": f"Bearer {nosub_token}"})
            nosub_pet_id = nosub_pet_res.json().get("pet_id", "")
            
            nosub_res = requests.post(f"{BASE_URL}/api/bookings", json={
                "provider_id": provider_id,
                "service_type": "paseo",
                "start_date": (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z",
                "pet_ids": [nosub_pet_id] if nosub_pet_id else []
            }, headers={"Authorization": f"Bearer {nosub_token}"})
            assert nosub_res.status_code == 403, f"Expected 403 without subscription, got {nosub_res.status_code}: {nosub_res.text}"
            print("  ✓ Booking without subscription returns 403")
        
        # 6. Create booking
        start_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        booking_res = requests.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": provider_id,
            "service_type": "paseo",
            "start_date": start_date,
            "pet_ids": [pet_id],
            "notes": "Test booking"
        }, headers={"Authorization": f"Bearer {client_token}"})
        
        assert booking_res.status_code == 200, f"Booking creation failed: {booking_res.text}"
        booking = booking_res.json()
        booking_id = booking["booking_id"]
        assert booking["status"] == "pending"
        assert booking["service_type"] == "paseo"
        assert len(booking.get("pets", [])) == 1
        print(f"  ✓ Booking created: {booking_id}, status: pending")
        
        # 7. Test get my bookings (client)
        my_res = requests.get(f"{BASE_URL}/api/bookings/my",
            headers={"Authorization": f"Bearer {client_token}"})
        assert my_res.status_code == 200
        bookings = my_res.json()
        assert isinstance(bookings, list)
        assert len(bookings) >= 1
        print(f"  ✓ Get my bookings: {len(bookings)} bookings")
        
        # 8. Test get provider bookings
        prov_bookings_res = requests.get(f"{BASE_URL}/api/bookings/provider",
            headers={"Authorization": f"Bearer {provider_token}"})
        assert prov_bookings_res.status_code == 200
        prov_bookings = prov_bookings_res.json()
        assert isinstance(prov_bookings, list)
        our_booking = next((b for b in prov_bookings if b["booking_id"] == booking_id), None)
        assert our_booking is not None, "Booking should appear in provider's list"
        print(f"  ✓ Get provider bookings: {len(prov_bookings)} bookings")
        
        # 9. Test get booking details
        detail_res = requests.get(f"{BASE_URL}/api/bookings/{booking_id}",
            headers={"Authorization": f"Bearer {client_token}"})
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["booking_id"] == booking_id
        assert "pets" in detail
        print("  ✓ Get booking details OK")
        
        # 10. Confirm booking as provider
        confirm_res = requests.put(f"{BASE_URL}/api/bookings/{booking_id}/respond", json={
            "status": "confirmed",
            "provider_notes": "Looking forward to it!"
        }, headers={"Authorization": f"Bearer {provider_token}"})
        assert confirm_res.status_code == 200, f"Confirm failed: {confirm_res.text}"
        assert "confirmada" in confirm_res.json().get("message", "").lower()
        print("  ✓ Booking confirmed by provider")
        
        # 11. Complete booking
        complete_res = requests.put(f"{BASE_URL}/api/bookings/{booking_id}/complete",
            headers={"Authorization": f"Bearer {provider_token}"})
        assert complete_res.status_code == 200, f"Complete failed: {complete_res.text}"
        assert "completada" in complete_res.json().get("message", "").lower()
        print("  ✓ Booking completed by provider")
        
        # 12. Verify final status
        final_res = requests.get(f"{BASE_URL}/api/bookings/{booking_id}",
            headers={"Authorization": f"Bearer {client_token}"})
        assert final_res.status_code == 200
        assert final_res.json()["status"] == "completed"
        print("  ✓ Final status verified: completed")
        
        # 13. Test booking stats
        stats_res = requests.get(f"{BASE_URL}/api/bookings/stats/summary",
            headers={"Authorization": f"Bearer {provider_token}"})
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert "pending" in stats
        assert "confirmed" in stats
        assert "completed" in stats
        assert "total" in stats
        print(f"  ✓ Booking stats: total={stats['total']}, completed={stats['completed']}")
        
        print("\n✓ Full booking flow test PASSED!")
        
    finally:
        mongo.close()


def test_booking_reject_flow():
    """Test booking rejection flow"""
    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    password = "testpass123456"
    unique_id = uuid.uuid4().hex[:6]
    
    try:
        # Create fresh client and provider
        client_email = f"{TEST_PREFIX}reject_client_{unique_id}@test.com"
        client_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": client_email,
            "password": password,
            "name": "Reject Test Client",
            "role": "client"
        })
        assert client_res.status_code == 200
        client_token = client_res.json()["token"]
        client_user_id = client_res.json()["user"]["user_id"]
        
        # Grant subscription
        db.subscriptions.update_one(
            {"user_id": client_user_id},
            {"$set": {
                "user_id": client_user_id,
                "plan_id": "plan_test",
                "status": "active",
                "start_date": datetime.utcnow(),
                "end_date": datetime.utcnow() + timedelta(days=30)
            }},
            upsert=True
        )
        
        provider_email = f"{TEST_PREFIX}reject_provider_{unique_id}@test.com"
        prov_reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": provider_email,
            "password": password,
            "name": "Reject Test Provider",
            "role": "client"
        })
        provider_token = prov_reg_res.json()["token"]
        
        prov_res = requests.post(f"{BASE_URL}/api/providers", json={
            "business_name": "Reject Test Carer",
            "description": "Test",
            "address": "Test Address",
            "comuna": "Santiago",
            "phone": "+56912345678",
            "services_offered": [{"service_type": "paseo", "price_from": 10000, "pet_sizes": ["mediano"]}]
        }, headers={"Authorization": f"Bearer {provider_token}"})
        provider_id = prov_res.json()["provider_id"]
        
        # Create pet
        pet_res = requests.post(f"{BASE_URL}/api/pets", json={
            "name": "RejectDog",
            "species": "perro",
            "size": "mediano",
            "sex": "macho"
        }, headers={"Authorization": f"Bearer {client_token}"})
        pet_id = pet_res.json()["pet_id"]
        
        # Create booking
        start_date = (datetime.utcnow() + timedelta(days=20)).isoformat() + "Z"
        booking_res = requests.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": provider_id,
            "service_type": "paseo",
            "start_date": start_date,
            "pet_ids": [pet_id]
        }, headers={"Authorization": f"Bearer {client_token}"})
        
        assert booking_res.status_code == 200
        booking_id = booking_res.json()["booking_id"]
        print(f"  ✓ Booking created: {booking_id}")
        
        # Reject booking
        reject_res = requests.put(f"{BASE_URL}/api/bookings/{booking_id}/respond", json={
            "status": "rejected",
            "provider_notes": "Not available on that date"
        }, headers={"Authorization": f"Bearer {provider_token}"})
        
        assert reject_res.status_code == 200
        assert "rechazada" in reject_res.json().get("message", "").lower()
        print("  ✓ Booking rejected")
        
        # Verify status
        detail_res = requests.get(f"{BASE_URL}/api/bookings/{booking_id}",
            headers={"Authorization": f"Bearer {client_token}"})
        assert detail_res.json()["status"] == "rejected"
        print("  ✓ Final status: rejected")
        
        print("\n✓ Booking reject flow test PASSED!")
        
    finally:
        mongo.close()


def test_booking_cancel_flow():
    """Test booking cancellation by client"""
    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    password = "testpass123456"
    unique_id = uuid.uuid4().hex[:6]
    
    try:
        # Create fresh client and provider
        client_email = f"{TEST_PREFIX}cancel_client_{unique_id}@test.com"
        client_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": client_email,
            "password": password,
            "name": "Cancel Test Client",
            "role": "client"
        })
        assert client_res.status_code == 200
        client_token = client_res.json()["token"]
        client_user_id = client_res.json()["user"]["user_id"]
        
        db.subscriptions.update_one(
            {"user_id": client_user_id},
            {"$set": {
                "user_id": client_user_id,
                "plan_id": "plan_test",
                "status": "active",
                "start_date": datetime.utcnow(),
                "end_date": datetime.utcnow() + timedelta(days=30)
            }},
            upsert=True
        )
        
        provider_email = f"{TEST_PREFIX}cancel_provider_{unique_id}@test.com"
        prov_reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": provider_email,
            "password": password,
            "name": "Cancel Test Provider",
            "role": "client"
        })
        provider_token = prov_reg_res.json()["token"]
        
        prov_res = requests.post(f"{BASE_URL}/api/providers", json={
            "business_name": "Cancel Test Carer",
            "description": "Test",
            "address": "Test Address",
            "comuna": "Santiago",
            "phone": "+56912345678",
            "services_offered": [{"service_type": "paseo", "price_from": 10000, "pet_sizes": ["mediano"]}]
        }, headers={"Authorization": f"Bearer {provider_token}"})
        provider_id = prov_res.json()["provider_id"]
        
        # Create pet
        pet_res = requests.post(f"{BASE_URL}/api/pets", json={
            "name": "CancelDog",
            "species": "perro",
            "size": "mediano",
            "sex": "macho"
        }, headers={"Authorization": f"Bearer {client_token}"})
        pet_id = pet_res.json()["pet_id"]
        
        # Create booking
        start_date = (datetime.utcnow() + timedelta(days=21)).isoformat() + "Z"
        booking_res = requests.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": provider_id,
            "service_type": "paseo",
            "start_date": start_date,
            "pet_ids": [pet_id]
        }, headers={"Authorization": f"Bearer {client_token}"})
        
        booking_id = booking_res.json()["booking_id"]
        print(f"  ✓ Booking created: {booking_id}")
        
        # Cancel booking
        cancel_res = requests.put(f"{BASE_URL}/api/bookings/{booking_id}/cancel",
            headers={"Authorization": f"Bearer {client_token}"})
        
        assert cancel_res.status_code == 200
        assert "cancelada" in cancel_res.json().get("message", "").lower()
        print("  ✓ Booking cancelled by client")
        
        # Verify provider cannot cancel client's booking
        start_date2 = (datetime.utcnow() + timedelta(days=22)).isoformat() + "Z"
        booking_res2 = requests.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": provider_id,
            "service_type": "paseo",
            "start_date": start_date2,
            "pet_ids": [pet_id]
        }, headers={"Authorization": f"Bearer {client_token}"})
        booking_id2 = booking_res2.json()["booking_id"]
        
        cancel_res2 = requests.put(f"{BASE_URL}/api/bookings/{booking_id2}/cancel",
            headers={"Authorization": f"Bearer {provider_token}"})
        assert cancel_res2.status_code == 404, f"Expected 404, got {cancel_res2.status_code}"
        print("  ✓ Provider cannot cancel client's booking (404)")
        
        print("\n✓ Booking cancel flow test PASSED!")
        
    finally:
        mongo.close()


def test_complete_pending_booking_fails():
    """Test that completing a pending booking fails"""
    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    password = "testpass123456"
    unique_id = uuid.uuid4().hex[:6]
    
    try:
        # Create fresh users
        client_email = f"{TEST_PREFIX}pend_client_{unique_id}@test.com"
        client_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": client_email,
            "password": password,
            "name": "Pending Test Client",
            "role": "client"
        })
        client_token = client_res.json()["token"]
        client_user_id = client_res.json()["user"]["user_id"]
        
        db.subscriptions.update_one(
            {"user_id": client_user_id},
            {"$set": {
                "user_id": client_user_id,
                "plan_id": "plan_test",
                "status": "active",
                "start_date": datetime.utcnow(),
                "end_date": datetime.utcnow() + timedelta(days=30)
            }},
            upsert=True
        )
        
        provider_email = f"{TEST_PREFIX}pend_provider_{unique_id}@test.com"
        prov_reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": provider_email,
            "password": password,
            "name": "Pending Test Provider",
            "role": "client"
        })
        provider_token = prov_reg_res.json()["token"]
        
        prov_res = requests.post(f"{BASE_URL}/api/providers", json={
            "business_name": "Pending Test Carer",
            "description": "Test",
            "address": "Test Address",
            "comuna": "Santiago",
            "phone": "+56912345678",
            "services_offered": [{"service_type": "paseo", "price_from": 10000, "pet_sizes": ["mediano"]}]
        }, headers={"Authorization": f"Bearer {provider_token}"})
        provider_id = prov_res.json()["provider_id"]
        
        pet_res = requests.post(f"{BASE_URL}/api/pets", json={
            "name": "PendDog",
            "species": "perro",
            "size": "mediano",
            "sex": "macho"
        }, headers={"Authorization": f"Bearer {client_token}"})
        pet_id = pet_res.json()["pet_id"]
        
        # Create pending booking
        start_date = (datetime.utcnow() + timedelta(days=25)).isoformat() + "Z"
        booking_res = requests.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": provider_id,
            "service_type": "paseo",
            "start_date": start_date,
            "pet_ids": [pet_id]
        }, headers={"Authorization": f"Bearer {client_token}"})
        
        booking_id = booking_res.json()["booking_id"]
        
        # Try to complete pending booking
        complete_res = requests.put(f"{BASE_URL}/api/bookings/{booking_id}/complete",
            headers={"Authorization": f"Bearer {provider_token}"})
        
        assert complete_res.status_code == 400, f"Expected 400, got {complete_res.status_code}"
        print("  ✓ Complete pending booking returns 400")
        
        print("\n✓ Complete pending booking test PASSED!")
        
    finally:
        mongo.close()


def test_invalid_provider_and_pet():
    """Test booking with invalid provider and pet"""
    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    password = "testpass123456"
    unique_id = uuid.uuid4().hex[:6]
    
    try:
        # Create client with subscription
        client_email = f"{TEST_PREFIX}inv_client_{unique_id}@test.com"
        client_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": client_email,
            "password": password,
            "name": "Invalid Test Client",
            "role": "client"
        })
        client_token = client_res.json()["token"]
        client_user_id = client_res.json()["user"]["user_id"]
        
        db.subscriptions.update_one(
            {"user_id": client_user_id},
            {"$set": {
                "user_id": client_user_id,
                "plan_id": "plan_test",
                "status": "active",
                "start_date": datetime.utcnow(),
                "end_date": datetime.utcnow() + timedelta(days=30)
            }},
            upsert=True
        )
        
        # Get a valid provider
        provider_email = f"{TEST_PREFIX}inv_provider_{unique_id}@test.com"
        prov_reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": provider_email,
            "password": password,
            "name": "Invalid Test Provider",
            "role": "client"
        })
        provider_token = prov_reg_res.json()["token"]
        
        prov_res = requests.post(f"{BASE_URL}/api/providers", json={
            "business_name": "Invalid Test Carer",
            "description": "Test",
            "address": "Test Address",
            "comuna": "Santiago",
            "phone": "+56912345678",
            "services_offered": [{"service_type": "paseo", "price_from": 10000, "pet_sizes": ["mediano"]}]
        }, headers={"Authorization": f"Bearer {provider_token}"})
        provider_id = prov_res.json()["provider_id"]
        
        start_date = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
        
        # Test invalid provider
        res = requests.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": "invalid_provider_xyz",
            "service_type": "paseo",
            "start_date": start_date,
            "pet_ids": []
        }, headers={"Authorization": f"Bearer {client_token}"})
        
        assert res.status_code == 404, f"Expected 404 for invalid provider, got {res.status_code}"
        print("  ✓ Invalid provider returns 404")
        
        # Test invalid pet
        res2 = requests.post(f"{BASE_URL}/api/bookings", json={
            "provider_id": provider_id,
            "service_type": "paseo",
            "start_date": start_date,
            "pet_ids": ["invalid_pet_xyz"]
        }, headers={"Authorization": f"Bearer {client_token}"})
        
        assert res2.status_code == 400, f"Expected 400 for invalid pet, got {res2.status_code}"
        print("  ✓ Invalid pet returns 400")
        
        print("\n✓ Invalid provider/pet test PASSED!")
        
    finally:
        mongo.close()


def test_get_client_requires_provider_profile():
    """Test that client cannot access provider endpoints"""
    mongo = MongoClient(MONGO_URL)
    db = mongo[DB_NAME]
    password = "testpass123456"
    unique_id = uuid.uuid4().hex[:6]
    
    try:
        # Create client only (no provider profile)
        client_email = f"{TEST_PREFIX}cli_only_{unique_id}@test.com"
        client_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": client_email,
            "password": password,
            "name": "Client Only",
            "role": "client"
        })
        client_token = client_res.json()["token"]
        
        # Client should not access provider bookings
        res = requests.get(f"{BASE_URL}/api/bookings/provider",
            headers={"Authorization": f"Bearer {client_token}"})
        assert res.status_code == 404, f"Expected 404, got {res.status_code}"
        print("  ✓ Client cannot access provider bookings (404)")
        
        # Client should not access booking stats
        res2 = requests.get(f"{BASE_URL}/api/bookings/stats/summary",
            headers={"Authorization": f"Bearer {client_token}"})
        assert res2.status_code == 404, f"Expected 404, got {res2.status_code}"
        print("  ✓ Client cannot access booking stats (404)")
        
        print("\n✓ Provider profile required test PASSED!")
        
    finally:
        mongo.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
