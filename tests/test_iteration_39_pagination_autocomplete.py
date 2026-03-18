"""
Iteration 39 - Pagination and Autocomplete Tests
Tests for:
- GET /api/providers with pagination (skip, limit) returning {results, total, skip, limit}
- GET /api/providers/comunas returning distinct comunas
- Filtering by comuna with pagination
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestProvidersPagination:
    """Tests for pagination in /api/providers endpoint"""
    
    def test_providers_returns_paginated_format(self):
        """GET /api/providers returns {results, total, skip, limit} format"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data, "Response should have 'results' key"
        assert "total" in data, "Response should have 'total' key"
        assert "skip" in data, "Response should have 'skip' key"
        assert "limit" in data, "Response should have 'limit' key"
        
        assert isinstance(data["results"], list), "results should be a list"
        assert isinstance(data["total"], int), "total should be an integer"
        assert isinstance(data["skip"], int), "skip should be an integer"
        assert isinstance(data["limit"], int), "limit should be an integer"
        print(f"✓ Response format correct: total={data['total']}, skip={data['skip']}, limit={data['limit']}, results_count={len(data['results'])}")
    
    def test_providers_pagination_skip_limit_5(self):
        """GET /api/providers?skip=0&limit=5 returns exactly 5 results"""
        response = requests.get(f"{BASE_URL}/api/providers?skip=0&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) == 5, f"Expected 5 results, got {len(data['results'])}"
        assert data["skip"] == 0, "skip should be 0"
        assert data["limit"] == 5, "limit should be 5"
        assert data["total"] >= 5, f"Total should be at least 5, got {data['total']}"
        print(f"✓ Page 1: Got {len(data['results'])} results, total={data['total']}")
        
        # Return first provider ids to verify no overlap with page 2
        return [p.get("provider_id") for p in data["results"]]
    
    def test_providers_pagination_page_2(self):
        """GET /api/providers?skip=5&limit=5 returns next 5 results (page 2)"""
        # Get page 1
        page1_response = requests.get(f"{BASE_URL}/api/providers?skip=0&limit=5")
        assert page1_response.status_code == 200
        page1_ids = [p.get("provider_id") for p in page1_response.json()["results"]]
        
        # Get page 2
        page2_response = requests.get(f"{BASE_URL}/api/providers?skip=5&limit=5")
        assert page2_response.status_code == 200
        
        data = page2_response.json()
        assert len(data["results"]) == 5, f"Expected 5 results on page 2, got {len(data['results'])}"
        assert data["skip"] == 5, "skip should be 5 for page 2"
        assert data["limit"] == 5, "limit should be 5"
        
        # Verify page 2 has different providers than page 1
        page2_ids = [p.get("provider_id") for p in data["results"]]
        overlap = set(page1_ids) & set(page2_ids)
        assert len(overlap) == 0, f"Page 1 and Page 2 should have no overlap, found: {overlap}"
        print(f"✓ Page 2: Got {len(data['results'])} different results from page 1")
    
    def test_providers_pagination_large_skip(self):
        """GET /api/providers?skip=200&limit=20 returns results or empty with total"""
        response = requests.get(f"{BASE_URL}/api/providers?skip=200&limit=20")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        # If total < 200+20, results may be partial or empty
        if data["total"] < 200:
            assert len(data["results"]) == 0, "Results should be empty if skip exceeds total"
        else:
            assert len(data["results"]) <= 20
        print(f"✓ Large skip: Got {len(data['results'])} results, total={data['total']}")
    
    def test_providers_default_pagination(self):
        """GET /api/providers without params uses default limit (50)"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        
        data = response.json()
        assert data["skip"] == 0, "Default skip should be 0"
        assert data["limit"] == 50, "Default limit should be 50"
        assert len(data["results"]) <= 50
        print(f"✓ Default pagination: skip={data['skip']}, limit={data['limit']}, results={len(data['results'])}")


class TestComunasAutocomplete:
    """Tests for /api/providers/comunas endpoint"""
    
    def test_comunas_endpoint_returns_list(self):
        """GET /api/providers/comunas returns array of distinct comunas"""
        response = requests.get(f"{BASE_URL}/api/providers/comunas")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of comunas"
        assert len(data) > 0, "Should have at least one comuna"
        
        # Check all items are strings
        for comuna in data:
            assert isinstance(comuna, str), f"Each comuna should be a string, got {type(comuna)}"
            assert len(comuna.strip()) > 0, "Comuna should not be empty"
        
        print(f"✓ Comunas endpoint returns {len(data)} distinct comunas")
        return data
    
    def test_comunas_are_sorted(self):
        """GET /api/providers/comunas returns sorted list"""
        response = requests.get(f"{BASE_URL}/api/providers/comunas")
        assert response.status_code == 200
        
        data = response.json()
        sorted_data = sorted(data)
        assert data == sorted_data, "Comunas should be sorted alphabetically"
        print(f"✓ Comunas are sorted: first='{data[0]}', last='{data[-1]}'")
    
    def test_comunas_has_expected_count(self):
        """GET /api/providers/comunas returns approximately 34 comunas (as per context)"""
        response = requests.get(f"{BASE_URL}/api/providers/comunas")
        assert response.status_code == 200
        
        data = response.json()
        # Context mentions 34 distinct comunas
        assert len(data) >= 20, f"Expected at least 20 comunas, got {len(data)}"
        print(f"✓ Found {len(data)} distinct comunas")


class TestFilteredPaginationComuna:
    """Tests for filtering by comuna with pagination"""
    
    def test_filter_by_comuna_with_pagination(self):
        """GET /api/providers?comuna=Las+Condes returns filtered results with total count"""
        response = requests.get(f"{BASE_URL}/api/providers?comuna=Las+Condes")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        
        # All results should match the comuna filter
        for provider in data["results"]:
            comuna = provider.get("comuna", "")
            assert "Las Condes" in comuna or "las condes" in comuna.lower(), \
                f"Provider comuna '{comuna}' doesn't match filter 'Las Condes'"
        
        print(f"✓ Filter by comuna 'Las Condes': {len(data['results'])} results, total={data['total']}")
    
    def test_filter_by_comuna_partial_match(self):
        """GET /api/providers?comuna=Santiago returns providers with 'Santiago' in comuna"""
        response = requests.get(f"{BASE_URL}/api/providers?comuna=Santiago")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        
        # Check that results contain 'Santiago' (could be 'Santiago Centro', 'Santiago', etc.)
        for provider in data["results"]:
            comuna = provider.get("comuna", "").lower()
            assert "santiago" in comuna, f"Provider comuna '{provider.get('comuna')}' doesn't contain 'Santiago'"
        
        print(f"✓ Filter by 'Santiago': {len(data['results'])} results, total={data['total']}")
    
    def test_filter_and_paginate_combined(self):
        """GET /api/providers?comuna=Las&skip=0&limit=5 returns paginated filtered results"""
        # First get total for filter
        full_response = requests.get(f"{BASE_URL}/api/providers?comuna=Las")
        assert full_response.status_code == 200
        full_total = full_response.json()["total"]
        
        # Now get paginated
        response = requests.get(f"{BASE_URL}/api/providers?comuna=Las&skip=0&limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == full_total, "Total should match regardless of pagination"
        assert len(data["results"]) <= 5
        assert data["skip"] == 0
        assert data["limit"] == 5
        print(f"✓ Filter+Pagination: {len(data['results'])} results out of total={data['total']}")
    
    def test_nonexistent_comuna_returns_empty(self):
        """GET /api/providers?comuna=NonexistentComuna returns empty results with total=0"""
        response = requests.get(f"{BASE_URL}/api/providers?comuna=ZZZNonexistentComuna123")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) == 0, "Should return empty results for non-existent comuna"
        assert data["total"] == 0, "Total should be 0 for non-existent comuna"
        print(f"✓ Non-existent comuna: {len(data['results'])} results, total={data['total']}")


class TestServiceTypeFilterWithPagination:
    """Tests for filtering by service_type with pagination"""
    
    def test_service_type_filter_residencias(self):
        """GET /api/providers?service_type=residencias returns filtered results"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=residencias")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        print(f"✓ Filter by service_type 'residencias': {len(data['results'])} results, total={data['total']}")
    
    def test_service_type_filter_cuidado_domicilio(self):
        """GET /api/providers?service_type=cuidado-domicilio returns filtered results"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=cuidado-domicilio")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        print(f"✓ Filter by service_type 'cuidado-domicilio': {len(data['results'])} results, total={data['total']}")
    
    def test_service_type_filter_salud_mental(self):
        """GET /api/providers?service_type=salud-mental returns filtered results"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=salud-mental")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        print(f"✓ Filter by service_type 'salud-mental': {len(data['results'])} results, total={data['total']}")
    
    def test_combined_service_and_comuna_filter(self):
        """GET /api/providers?service_type=residencias&comuna=Las returns combined filter"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=residencias&comuna=Las&limit=10")
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "total" in data
        print(f"✓ Combined filter (residencias + 'Las'): {len(data['results'])} results, total={data['total']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
