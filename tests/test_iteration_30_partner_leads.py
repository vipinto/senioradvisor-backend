"""
Test Iteration 30: Partner Leads API for SeniorClub feature
Tests POST /api/partners/leads and GET /api/partners/leads endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPartnerLeadsAPI:
    """Partner Leads CRUD Tests"""
    
    def test_create_lead_full_fields(self):
        """Test creating a lead with all fields"""
        lead_data = {
            "partner_slug": "help-rescate",
            "name": f"TEST_Lead_{uuid.uuid4().hex[:6]}",
            "email": f"test_{uuid.uuid4().hex[:6]}@test.cl",
            "phone": "912345678",
            "contact_type": "cotizacion",
            "plan_interest": "Plan Hogar"
        }
        
        response = requests.post(f"{BASE_URL}/api/partners/leads", json=lead_data)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "lead_id" in data, "Response should contain lead_id"
        assert data["name"] == lead_data["name"], "Name should match"
        assert data["email"] == lead_data["email"], "Email should match"
        assert data["phone"] == lead_data["phone"], "Phone should match"
        assert data["contact_type"] == lead_data["contact_type"], "Contact type should match"
        assert data["plan_interest"] == lead_data["plan_interest"], "Plan interest should match"
        assert data["partner_slug"] == "help-rescate", "Partner slug should match"
        assert data["status"] == "new", "Status should be 'new'"
        assert "created_at" in data, "Should have created_at timestamp"
        print(f"  PASS: Lead created with ID {data['lead_id']}")
    
    def test_create_lead_minimal_fields(self):
        """Test creating a lead with only required fields"""
        lead_data = {
            "partner_slug": "help-rescate",
            "name": f"TEST_Minimal_{uuid.uuid4().hex[:6]}",
            "email": f"minimal_{uuid.uuid4().hex[:6]}@test.cl",
            "phone": "987654321"
        }
        
        response = requests.post(f"{BASE_URL}/api/partners/leads", json=lead_data)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data["contact_type"] == "", "Contact type should default to empty string"
        assert data["plan_interest"] == "", "Plan interest should default to empty string"
        print(f"  PASS: Lead with minimal fields created")
    
    def test_create_lead_missing_required_field(self):
        """Test that missing required fields return error"""
        # Missing name
        lead_data = {
            "partner_slug": "help-rescate",
            "email": "test@test.cl",
            "phone": "912345678"
        }
        
        response = requests.post(f"{BASE_URL}/api/partners/leads", json=lead_data)
        
        assert response.status_code == 422, f"Expected 422 for validation error, got {response.status_code}"
        print(f"  PASS: Validation error returned for missing name")
    
    def test_get_all_leads(self):
        """Test getting all leads"""
        response = requests.get(f"{BASE_URL}/api/partners/leads")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"  PASS: Retrieved {len(data)} leads")
        
        # Verify structure of first lead if exists
        if len(data) > 0:
            first_lead = data[0]
            required_fields = ["lead_id", "partner_slug", "name", "email", "phone", "status", "created_at"]
            for field in required_fields:
                assert field in first_lead, f"Lead should have field '{field}'"
            print(f"  PASS: Lead structure verified")
    
    def test_get_leads_sorted_by_date_desc(self):
        """Test that leads are returned sorted by date descending (newest first)"""
        response = requests.get(f"{BASE_URL}/api/partners/leads")
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) >= 2:
            first_date = data[0]["created_at"]
            second_date = data[1]["created_at"]
            assert first_date >= second_date, "Leads should be sorted newest first"
            print(f"  PASS: Leads sorted by date descending")
        else:
            print(f"  SKIP: Not enough leads to verify sorting")
    
    def test_get_leads_by_partner_slug(self):
        """Test filtering leads by partner_slug"""
        response = requests.get(f"{BASE_URL}/api/partners/leads?partner_slug=help-rescate")
        
        assert response.status_code == 200
        data = response.json()
        
        for lead in data:
            assert lead["partner_slug"] == "help-rescate", "All leads should be for help-rescate"
        print(f"  PASS: Filter by partner_slug works - {len(data)} leads for help-rescate")
    
    def test_lead_stats_endpoint(self):
        """Test getting lead stats"""
        response = requests.get(f"{BASE_URL}/api/partners/leads/stats")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, dict), "Stats should be a dictionary"
        
        if "help-rescate" in data:
            assert isinstance(data["help-rescate"], int), "Count should be an integer"
            print(f"  PASS: Stats endpoint returns {data}")
        else:
            print(f"  PASS: Stats endpoint works, data: {data}")


class TestPartnerLeadsIntegration:
    """Integration tests - Create then GET to verify persistence"""
    
    def test_create_and_verify_persistence(self):
        """Test creating a lead and verifying it appears in GET list"""
        unique_id = uuid.uuid4().hex[:8]
        lead_data = {
            "partner_slug": "help-rescate",
            "name": f"TEST_Persistence_{unique_id}",
            "email": f"persist_{unique_id}@test.cl",
            "phone": "555555555",
            "contact_type": "informacion",
            "plan_interest": "Plan Rescate Total"
        }
        
        # Create lead
        create_response = requests.post(f"{BASE_URL}/api/partners/leads", json=lead_data)
        assert create_response.status_code == 200
        created_lead = create_response.json()
        lead_id = created_lead["lead_id"]
        
        # Verify it appears in GET list
        get_response = requests.get(f"{BASE_URL}/api/partners/leads")
        assert get_response.status_code == 200
        all_leads = get_response.json()
        
        found = False
        for lead in all_leads:
            if lead["lead_id"] == lead_id:
                found = True
                assert lead["name"] == lead_data["name"]
                assert lead["email"] == lead_data["email"]
                break
        
        assert found, f"Created lead {lead_id} should appear in GET list"
        print(f"  PASS: Lead {lead_id} persisted and retrieved successfully")
