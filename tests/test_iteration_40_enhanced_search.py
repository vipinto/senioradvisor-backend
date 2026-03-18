"""
Iteration 40: Enhanced Search Feature Tests
- Tests for new 'q' parameter that searches by name, address, or comuna
- Tests for combined filters (q + service_type)
- Tests for backwards compatibility (comuna param still works)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestEnhancedSearch:
    """Tests for enhanced search functionality using 'q' parameter"""
    
    def test_search_by_provider_name(self):
        """Search by provider name using q parameter - should find 'Residencia Los Aromos'"""
        response = requests.get(f"{BASE_URL}/api/providers?q=Aromos")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        # Should find at least 1 provider with 'Aromos' in name
        assert len(results) >= 1
        
        # Verify the result contains 'Aromos' in business_name
        found_aromos = any('Aromos' in p.get('business_name', '') for p in results)
        assert found_aromos, "Should find provider with 'Aromos' in name"
        
    def test_search_by_comuna_using_q(self):
        """Search by comuna using q parameter - should find providers in Las Condes"""
        response = requests.get(f"{BASE_URL}/api/providers?q=Las+Condes")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        total = data.get('total', len(results))
        
        # Should find multiple providers in Las Condes
        assert len(results) >= 1
        assert total >= 1
        
        # Verify results contain Las Condes
        has_las_condes = any('Las Condes' in (p.get('comuna', '') + p.get('address', '')) for p in results)
        assert has_las_condes, "Should find providers related to 'Las Condes'"
        
    def test_search_by_address_using_q(self):
        """Search by address using q parameter - should find providers in Providencia"""
        response = requests.get(f"{BASE_URL}/api/providers?q=Providencia")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        # Should find providers matching Providencia
        assert len(results) >= 1
        
    def test_combined_search_q_and_service_type(self):
        """Combined search: q=Aromos AND service_type=residencias - no $or conflict"""
        response = requests.get(f"{BASE_URL}/api/providers?q=Aromos&service_type=residencias")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        # Should find the provider with both criteria
        assert len(results) >= 1
        
        # Verify provider offers residencias service
        for provider in results:
            services = provider.get('services', [])
            has_residencias = any(s.get('service_type') == 'residencias' for s in services)
            # Provider should have residencias service or be filtered correctly
            assert has_residencias or len(services) == 0
            
    def test_no_q_param_returns_all_providers(self):
        """Without q parameter, should return all providers (default behavior)"""
        response = requests.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        total = data.get('total', len(results))
        
        # Should return all providers (263 as per previous tests)
        assert total >= 200
        # Default limit is 50
        assert len(results) <= 50
        
    def test_comunas_endpoint_still_works(self):
        """GET /providers/comunas should still return comunas list"""
        response = requests.get(f"{BASE_URL}/api/providers/comunas")
        assert response.status_code == 200
        comunas = response.json()
        
        # Should be a list of strings
        assert isinstance(comunas, list)
        assert len(comunas) >= 30  # ~34 comunas expected
        
        # Should be sorted
        assert comunas == sorted(comunas)
        
        # Should include known comunas
        assert 'Las Condes' in comunas
        
    def test_backwards_compatibility_comuna_param(self):
        """Original comuna parameter should still work"""
        response = requests.get(f"{BASE_URL}/api/providers?comuna=Las+Condes")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        # Should filter by comuna
        assert len(results) >= 1
        
    def test_search_partial_match(self):
        """Partial text match should work (case insensitive)"""
        response = requests.get(f"{BASE_URL}/api/providers?q=aromos")  # lowercase
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        # Should find provider (case insensitive)
        assert len(results) >= 1
        
    def test_search_no_results(self):
        """Search with no matches should return empty results"""
        response = requests.get(f"{BASE_URL}/api/providers?q=XYZ123NOMATCH")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        total = data.get('total', len(results))
        
        assert len(results) == 0
        assert total == 0
        
    def test_combined_q_and_pagination(self):
        """q parameter with pagination"""
        response = requests.get(f"{BASE_URL}/api/providers?q=Santiago&skip=0&limit=5")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        # Should respect limit
        assert len(results) <= 5
        
    def test_service_type_only_filter(self):
        """Service type filter without q param"""
        response = requests.get(f"{BASE_URL}/api/providers?service_type=residencias")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        # Should return providers with residencias service
        assert len(results) >= 1


class TestSearchResponseFormat:
    """Tests for response format consistency"""
    
    def test_response_has_pagination_fields(self):
        """Response should have results, total, skip, limit fields"""
        response = requests.get(f"{BASE_URL}/api/providers?q=Las")
        assert response.status_code == 200
        data = response.json()
        
        assert 'results' in data
        assert 'total' in data
        assert 'skip' in data
        assert 'limit' in data
        
    def test_provider_has_services_array(self):
        """Each provider should have services array"""
        response = requests.get(f"{BASE_URL}/api/providers?q=Aromos")
        assert response.status_code == 200
        data = response.json()
        results = data.get('results', data)
        
        if len(results) > 0:
            provider = results[0]
            assert 'services' in provider
            assert isinstance(provider['services'], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
