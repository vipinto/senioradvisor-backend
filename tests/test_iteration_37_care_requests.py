"""
Iteration 37 - Care Requests API Tests
Tests for the new comprehensive 'Solicitud de Servicio' form for senior care.
The form collects: service_type, patient_name, patient_age, patient_gender, 
relationship, room_type, special_needs array, urgency, budget_min, budget_max, 
comuna, region, description
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

# Test credentials
CLIENT_EMAIL = "demo@senioradvisor.cl"
CLIENT_PASSWORD = "demo123"


class TestCareRequestsAPI:
    """Tests for /api/care-requests endpoints with new senior care schema"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        self.created_request_id = None

    def _login_as_client(self):
        """Helper to login as client user"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            return True
        return False

    def test_create_care_request_unauthenticated(self):
        """POST /api/care-requests should return 401 without auth"""
        response = self.session.post(f"{BASE_URL}/api/care-requests", json={
            "service_type": "residencia",
            "patient_name": "Test Patient",
            "comuna": "Providencia",
            "description": "Test description"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/care-requests returns 401 without auth")

    def test_create_care_request_missing_patient_name(self):
        """POST /api/care-requests should validate patient_name is required"""
        assert self._login_as_client(), "Login failed"
        
        response = self.session.post(f"{BASE_URL}/api/care-requests", json={
            "service_type": "residencia",
            "patient_name": "",  # Empty
            "comuna": "Providencia",
            "description": "Test description"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "nombre" in data.get("detail", "").lower() or "paciente" in data.get("detail", "").lower()
        print("PASS: POST /api/care-requests validates patient_name is required")

    def test_create_care_request_missing_comuna(self):
        """POST /api/care-requests should validate comuna is required"""
        assert self._login_as_client(), "Login failed"
        
        response = self.session.post(f"{BASE_URL}/api/care-requests", json={
            "service_type": "residencia",
            "patient_name": "Test Patient",
            "comuna": "",  # Empty
            "description": "Test description"
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "comuna" in data.get("detail", "").lower()
        print("PASS: POST /api/care-requests validates comuna is required")

    def test_create_care_request_missing_description(self):
        """POST /api/care-requests should validate description is required"""
        assert self._login_as_client(), "Login failed"
        
        response = self.session.post(f"{BASE_URL}/api/care-requests", json={
            "service_type": "residencia",
            "patient_name": "Test Patient",
            "comuna": "Providencia",
            "description": ""  # Empty
        })
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        assert "descripción" in data.get("detail", "").lower() or "descripcion" in data.get("detail", "").lower()
        print("PASS: POST /api/care-requests validates description is required")

    def test_create_care_request_with_all_fields(self):
        """POST /api/care-requests should create a request with all new schema fields"""
        assert self._login_as_client(), "Login failed"
        
        payload = {
            "service_type": "residencia",
            "patient_name": "TEST_Maria Gonzalez",
            "patient_age": 78,
            "patient_gender": "femenino",
            "relationship": "hijo",
            "room_type": "individual",
            "special_needs": ["demencia", "movilidad_reducida", "medicacion_constante"],
            "urgency": "dentro_1_mes",
            "budget_min": 500000,
            "budget_max": 1500000,
            "comuna": "Providencia",
            "region": "Región Metropolitana",
            "description": "Buscamos residencia para mi madre con Alzheimer temprano. Necesita supervisión constante y ayuda con movilidad."
        }
        
        response = self.session.post(f"{BASE_URL}/api/care-requests", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Validate response contains all fields
        assert "request_id" in data, "Missing request_id in response"
        assert data["service_type"] == "residencia"
        assert data["patient_name"] == "TEST_Maria Gonzalez"
        assert data["patient_age"] == 78
        assert data["patient_gender"] == "femenino"
        assert data["relationship"] == "hijo"
        assert data["room_type"] == "individual"
        assert data["special_needs"] == ["demencia", "movilidad_reducida", "medicacion_constante"]
        assert data["urgency"] == "dentro_1_mes"
        assert data["budget_min"] == 500000
        assert data["budget_max"] == 1500000
        assert data["comuna"] == "Providencia"
        assert data["region"] == "Región Metropolitana"
        assert "Alzheimer" in data["description"]
        assert data["status"] == "active"
        
        self.created_request_id = data["request_id"]
        print(f"PASS: POST /api/care-requests creates request with all fields. ID: {self.created_request_id}")
        
        return data["request_id"]

    def test_get_my_requests_returns_new_schema(self):
        """GET /api/care-requests/my-requests should return requests with new schema"""
        assert self._login_as_client(), "Login failed"
        
        response = self.session.get(f"{BASE_URL}/api/care-requests/my-requests")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        
        # Find a request with new schema fields
        found_new_schema = False
        for req in data:
            if "patient_name" in req or "special_needs" in req:
                found_new_schema = True
                # Validate new fields exist
                assert "service_type" in req, "Missing service_type"
                assert "comuna" in req, "Missing comuna"
                assert "description" in req, "Missing description"
                break
        
        print(f"PASS: GET /api/care-requests/my-requests returns {len(data)} requests")
        if found_new_schema:
            print("PASS: Response includes new schema fields (patient_name, special_needs, etc)")
        return data

    def test_update_care_request_status(self):
        """PUT /api/care-requests/{id} should update status (pause/activate)"""
        assert self._login_as_client(), "Login failed"
        
        # First get existing requests to find one to update
        response = self.session.get(f"{BASE_URL}/api/care-requests/my-requests")
        assert response.status_code == 200
        requests_list = response.json()
        
        if not requests_list:
            pytest.skip("No existing requests to update")
        
        # Find an active request
        request_to_update = None
        for req in requests_list:
            if req.get("status") == "active":
                request_to_update = req
                break
        
        if not request_to_update:
            # Use first one
            request_to_update = requests_list[0]
        
        request_id = request_to_update["request_id"]
        
        # Try to pause it
        response = self.session.put(f"{BASE_URL}/api/care-requests/{request_id}", json={
            "status": "paused"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["status"] == "paused", f"Expected paused, got {data.get('status')}"
        print(f"PASS: PUT /api/care-requests/{request_id} status paused")
        
        # Activate it back
        response = self.session.put(f"{BASE_URL}/api/care-requests/{request_id}", json={
            "status": "active"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        print(f"PASS: PUT /api/care-requests/{request_id} status activated")

    def test_delete_care_request(self):
        """DELETE /api/care-requests/{id} should delete a care request"""
        assert self._login_as_client(), "Login failed"
        
        # Create a request to delete
        payload = {
            "service_type": "cuidado_domicilio",
            "patient_name": "TEST_Delete_Patient",
            "comuna": "Las Condes",
            "description": "Request to delete for testing"
        }
        
        response = self.session.post(f"{BASE_URL}/api/care-requests", json=payload)
        assert response.status_code == 200, f"Failed to create request: {response.text}"
        
        request_id = response.json()["request_id"]
        print(f"Created request {request_id} for deletion test")
        
        # Delete it
        response = self.session.delete(f"{BASE_URL}/api/care-requests/{request_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "eliminada" in data.get("message", "").lower() or "deleted" in data.get("message", "").lower()
        print(f"PASS: DELETE /api/care-requests/{request_id} deleted successfully")
        
        # Verify it's gone
        response = self.session.get(f"{BASE_URL}/api/care-requests/my-requests")
        requests_list = response.json()
        request_ids = [r["request_id"] for r in requests_list]
        assert request_id not in request_ids, "Deleted request still appears in list"
        print("PASS: Deleted request no longer appears in my-requests list")

    def test_create_care_request_cuidado_domicilio(self):
        """POST /api/care-requests should support cuidado_domicilio service type"""
        assert self._login_as_client(), "Login failed"
        
        payload = {
            "service_type": "cuidado_domicilio",
            "patient_name": "TEST_Pedro Lopez",
            "patient_age": 85,
            "patient_gender": "masculino",
            "relationship": "conyuge",
            "special_needs": ["oxigeno", "cuidado_nocturno"],
            "urgency": "inmediata",
            "budget_min": 300000,
            "budget_max": 600000,
            "comuna": "Las Condes",
            "region": "Región Metropolitana",
            "description": "Necesitamos cuidador a domicilio para mi esposo. Requiere oxígeno y supervisión nocturna."
        }
        
        response = self.session.post(f"{BASE_URL}/api/care-requests", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["service_type"] == "cuidado_domicilio"
        assert data["special_needs"] == ["oxigeno", "cuidado_nocturno"]
        print("PASS: Created cuidado_domicilio request successfully")
        
        # Clean up
        self.session.delete(f"{BASE_URL}/api/care-requests/{data['request_id']}")

    def test_create_care_request_salud_mental(self):
        """POST /api/care-requests should support salud_mental service type"""
        assert self._login_as_client(), "Login failed"
        
        payload = {
            "service_type": "salud_mental",
            "patient_name": "TEST_Ana Torres",
            "patient_age": 72,
            "patient_gender": "femenino",
            "relationship": "nieto",
            "special_needs": ["acompanamiento"],
            "urgency": "dentro_3_meses",
            "comuna": "Vitacura",
            "description": "Buscamos apoyo en salud mental para mi abuela que tiene depresión."
        }
        
        response = self.session.post(f"{BASE_URL}/api/care-requests", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["service_type"] == "salud_mental"
        print("PASS: Created salud_mental request successfully")
        
        # Clean up
        self.session.delete(f"{BASE_URL}/api/care-requests/{data['request_id']}")


class TestCareRequestsCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_requests(self):
        """Remove TEST_ prefixed care requests"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLIENT_EMAIL,
            "password": CLIENT_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Could not login for cleanup")
        
        token = response.json().get("token")
        session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get all requests
        response = session.get(f"{BASE_URL}/api/care-requests/my-requests")
        if response.status_code != 200:
            pytest.skip("Could not fetch requests for cleanup")
        
        requests_list = response.json()
        deleted_count = 0
        
        for req in requests_list:
            patient_name = req.get("patient_name", "")
            if patient_name.startswith("TEST_"):
                session.delete(f"{BASE_URL}/api/care-requests/{req['request_id']}")
                deleted_count += 1
        
        print(f"PASS: Cleanup - deleted {deleted_count} test requests")
