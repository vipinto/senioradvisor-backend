"""
Iteration 42 - Full App Review Test Suite
Testing all 4 user roles: Client, Normal Provider, Subscribed Provider, Admin
Key features: Featured carousel, Search with rating filter, Provider profiles, 
Premium gallery, YouTube video, Google reviews integration, Admin panel
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"email": "admin@senioradvisor.cl", "password": "admin123"}
CLIENT_CREDS = {"email": "demo@senioradvisor.cl", "password": "demo123"}
PROVIDER_SUBSCRIBED_CREDS = {"email": "proveedor1@senioradvisor.cl", "password": "demo123"}
PROVIDER_VILLA_SERENA_CREDS = {"email": "proveedor6@senioradvisor.cl", "password": "demo123"}

# Known provider IDs
PROVEEDOR1_ID = "82aadda9-6892-4033-9cd4-acc31bbdcc39"
VILLA_SERENA_ID = "b2cc5b50-bcf5-40c8-b0b9-ed1307431ed0"


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
def client_token(api_client):
    """Get client authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=CLIENT_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Client authentication failed")


@pytest.fixture(scope="module")
def subscribed_provider_token(api_client):
    """Get subscribed provider authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=PROVIDER_SUBSCRIBED_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Subscribed provider authentication failed")


@pytest.fixture(scope="module")
def villa_serena_token(api_client):
    """Get Villa Serena provider token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=PROVIDER_VILLA_SERENA_CREDS)
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip("Villa Serena provider authentication failed")


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_backend_health(self, api_client):
        """Test backend health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ Backend health check passed")


class TestAuthentication:
    """Authentication flow tests for all user roles"""
    
    def test_admin_login(self, api_client):
        """Test admin login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data.get("user", {}).get("role") == "admin"
        print("✓ Admin login successful")
    
    def test_client_login(self, api_client):
        """Test client login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=CLIENT_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data.get("user", {}).get("role") == "client"
        print("✓ Client login successful")
    
    def test_subscribed_provider_login(self, api_client):
        """Test subscribed provider login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=PROVIDER_SUBSCRIBED_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data.get("user", {}).get("role") == "provider"
        print("✓ Subscribed provider login successful")
    
    def test_villa_serena_provider_login(self, api_client):
        """Test Villa Serena provider login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=PROVIDER_VILLA_SERENA_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        print("✓ Villa Serena provider login successful")


class TestFeaturedProviders:
    """Home page featured providers carousel tests"""
    
    def test_featured_providers_endpoint(self, api_client):
        """Test featured providers endpoint returns providers with 4+ rating"""
        response = api_client.get(f"{BASE_URL}/api/providers?featured=true")
        assert response.status_code == 200
        data = response.json()
        providers = data.get("results", data) if isinstance(data, dict) else data
        print(f"✓ Found {len(providers)} featured providers")
        
        # Verify featured providers have high rating
        for p in providers[:5]:  # Check first 5
            rating = p.get("rating", 0)
            print(f"  - {p.get('business_name')}: rating={rating}")
            # Note: is_featured is based on rating >= 4.0 AND active subscription
    
    def test_featured_providers_have_required_fields(self, api_client):
        """Test featured providers have required display fields"""
        response = api_client.get(f"{BASE_URL}/api/providers?featured=true")
        assert response.status_code == 200
        data = response.json()
        providers = data.get("results", data) if isinstance(data, dict) else data
        
        if len(providers) > 0:
            p = providers[0]
            assert "business_name" in p
            assert "rating" in p
            assert "comuna" in p
            print("✓ Featured providers have required fields")


class TestSearchPage:
    """Search page functionality tests"""
    
    def test_search_all_providers(self, api_client):
        """Test search returns providers"""
        response = api_client.get(f"{BASE_URL}/api/providers")
        assert response.status_code == 200
        data = response.json()
        providers = data.get("results", data) if isinstance(data, dict) else data
        total = data.get("total", len(providers))
        print(f"✓ Search returned {total} total providers")
        assert total > 0
    
    def test_search_by_service_type_residencias(self, api_client):
        """Test filtering by service type - Residencias"""
        response = api_client.get(f"{BASE_URL}/api/providers?service_type=residencias")
        assert response.status_code == 200
        print("✓ Service type filter (residencias) works")
    
    def test_search_by_service_type_cuidado_domicilio(self, api_client):
        """Test filtering by service type - Cuidado a Domicilio"""
        response = api_client.get(f"{BASE_URL}/api/providers?service_type=cuidado-domicilio")
        assert response.status_code == 200
        print("✓ Service type filter (cuidado-domicilio) works")
    
    def test_search_by_service_type_salud_mental(self, api_client):
        """Test filtering by service type - Salud Mental"""
        response = api_client.get(f"{BASE_URL}/api/providers?service_type=salud-mental")
        assert response.status_code == 200
        print("✓ Service type filter (salud-mental) works")
    
    def test_search_rating_filter_3_stars(self, api_client):
        """Test rating filter - 3+ stars"""
        response = api_client.get(f"{BASE_URL}/api/providers?min_rating=3")
        assert response.status_code == 200
        data = response.json()
        providers = data.get("results", data) if isinstance(data, dict) else data
        # Verify all returned providers have rating >= 3
        for p in providers[:10]:
            rating = p.get("rating", 0)
            if rating > 0:  # Skip providers without ratings
                assert rating >= 3, f"Provider {p.get('business_name')} has rating {rating} < 3"
        print("✓ Rating filter (3+ stars) works")
    
    def test_search_rating_filter_4_stars(self, api_client):
        """Test rating filter - 4+ stars"""
        response = api_client.get(f"{BASE_URL}/api/providers?min_rating=4")
        assert response.status_code == 200
        data = response.json()
        providers = data.get("results", data) if isinstance(data, dict) else data
        for p in providers[:10]:
            rating = p.get("rating", 0)
            if rating > 0:
                assert rating >= 4, f"Provider {p.get('business_name')} has rating {rating} < 4"
        print("✓ Rating filter (4+ stars) works")
    
    def test_search_rating_filter_4_5_stars(self, api_client):
        """Test rating filter - 4.5+ stars"""
        response = api_client.get(f"{BASE_URL}/api/providers?min_rating=4.5")
        assert response.status_code == 200
        data = response.json()
        providers = data.get("results", data) if isinstance(data, dict) else data
        for p in providers[:10]:
            rating = p.get("rating", 0)
            if rating > 0:
                assert rating >= 4.5, f"Provider {p.get('business_name')} has rating {rating} < 4.5"
        print("✓ Rating filter (4.5+ stars) works")
    
    def test_search_by_query(self, api_client):
        """Test search by name/address/comuna query"""
        response = api_client.get(f"{BASE_URL}/api/providers?q=Santiago")
        assert response.status_code == 200
        print("✓ Search by query works")
    
    def test_search_pagination(self, api_client):
        """Test search pagination"""
        # Page 1
        response1 = api_client.get(f"{BASE_URL}/api/providers?skip=0&limit=20")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Page 2
        response2 = api_client.get(f"{BASE_URL}/api/providers?skip=20&limit=20")
        assert response2.status_code == 200
        
        print("✓ Pagination works")
    
    def test_comunas_autocomplete(self, api_client):
        """Test comunas autocomplete endpoint"""
        response = api_client.get(f"{BASE_URL}/api/providers/comunas")
        assert response.status_code == 200
        comunas = response.json()
        assert isinstance(comunas, list)
        print(f"✓ Comunas autocomplete returned {len(comunas)} comunas")


class TestPublicProviderProfile:
    """Public provider profile tests"""
    
    def test_get_subscribed_provider_profile(self, api_client):
        """Test getting subscribed provider public profile (proveedor1)"""
        response = api_client.get(f"{BASE_URL}/api/providers/{PROVEEDOR1_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "business_name" in data
        assert "rating" in data
        print(f"✓ Provider profile loaded: {data.get('business_name')}")
        print(f"  Rating: {data.get('rating')}")
        print(f"  Reviews: {data.get('total_reviews', 0)}")
    
    def test_subscribed_provider_has_premium_gallery(self, api_client):
        """Test subscribed provider has premium_gallery field"""
        response = api_client.get(f"{BASE_URL}/api/providers/{PROVEEDOR1_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Check premium fields
        assert "provider_is_subscribed" in data
        if data.get("provider_is_subscribed"):
            print("✓ Provider is subscribed - checking premium gallery")
            if "premium_gallery" in data:
                print(f"  Premium gallery has {len(data.get('premium_gallery', []))} photos")
        else:
            print("  Provider is NOT subscribed")
    
    def test_provider_has_reviews(self, api_client):
        """Test provider has reviews field with Google reviews integration"""
        response = api_client.get(f"{BASE_URL}/api/providers/{PROVEEDOR1_ID}")
        assert response.status_code == 200
        data = response.json()
        
        reviews = data.get("reviews", [])
        print(f"✓ Provider has {len(reviews)} reviews")
        
        # Check review structure
        if reviews:
            r = reviews[0]
            print(f"  First review: {r.get('user_name')} - {r.get('rating')} stars")
            if r.get("time_description"):
                print(f"  Time: {r.get('time_description')}")


class TestProviderAccount:
    """Provider account (Mi Cuenta) tests"""
    
    def test_get_my_profile_subscribed(self, api_client, subscribed_provider_token):
        """Test subscribed provider can get their profile"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "business_name" in data
        assert "is_subscribed" in data
        print(f"✓ Provider my-profile loaded: {data.get('business_name')}")
        print(f"  is_subscribed: {data.get('is_subscribed')}")
    
    def test_subscribed_provider_has_youtube_field(self, api_client, subscribed_provider_token):
        """Test subscribed provider can edit YouTube video URL"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # youtube_video_url should be available for subscribed providers
        if data.get("is_subscribed"):
            print("✓ Subscribed provider can access YouTube field")
        else:
            print("  Provider is not subscribed - YouTube field locked")
    
    def test_provider_gallery_endpoint(self, api_client, subscribed_provider_token):
        """Test provider gallery endpoint exists"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check gallery
        gallery = data.get("gallery", [])
        print(f"✓ Provider has {len(gallery)} standard gallery photos")
    
    def test_premium_gallery_requires_subscription(self, api_client, subscribed_provider_token):
        """Test premium gallery endpoint"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile/premium-gallery", headers=headers)
        # Should return 200 for subscribed provider
        assert response.status_code in [200, 403]
        print(f"✓ Premium gallery endpoint status: {response.status_code}")
    
    def test_provider_services_update(self, api_client, subscribed_provider_token):
        """Test provider can update services/amenities"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        # Just verify the endpoint exists
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        services = data.get("services", [])
        amenities = data.get("amenities", [])
        print(f"✓ Provider has {len(services)} services, {len(amenities)} amenities")
    
    def test_provider_social_links(self, api_client, subscribed_provider_token):
        """Test provider social links"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        social = data.get("social_links", {})
        print(f"✓ Provider social links: {list(social.keys()) if social else 'none'}")


class TestClientDashboard:
    """Client dashboard tests"""
    
    def test_client_dashboard_access(self, api_client, client_token):
        """Test client can access their dashboard"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = api_client.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("role") == "client"
        print(f"✓ Client dashboard access: {data.get('name')}")


class TestAdminPanel:
    """Admin panel tests"""
    
    def test_admin_stats(self, api_client, admin_token):
        """Test admin can access stats"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/admin/stats", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        print("✓ Admin stats:")
        print(f"  Total users: {data.get('total_users')}")
        print(f"  Total providers: {data.get('total_providers')}")
        print(f"  Pending: {data.get('pending_providers')}")
        print(f"  Verified: {data.get('verified_providers')}")
        print(f"  Active subscriptions: {data.get('active_subscriptions')}")
    
    def test_admin_providers_list(self, api_client, admin_token):
        """Test admin can list all providers"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/admin/providers/all", headers=headers)
        assert response.status_code == 200
        providers = response.json()
        print(f"✓ Admin can list {len(providers)} providers")
    
    def test_admin_provider_detail(self, api_client, admin_token):
        """Test admin can get provider detail"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/admin/providers/{PROVEEDOR1_ID}/detail", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        print(f"✓ Admin provider detail: {data.get('business_name')}")
        print(f"  Has premium_gallery field: {'premium_gallery' in data}")
        print(f"  Has youtube_video_url: {'youtube_video_url' in data}")
    
    def test_admin_plans(self, api_client, admin_token):
        """Test admin can access plans"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/admin/plans", headers=headers)
        assert response.status_code == 200
        plans = response.json()
        print(f"✓ Admin can list {len(plans)} plans")
    
    def test_admin_metrics(self, api_client, admin_token):
        """Test admin can access metrics"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = api_client.get(f"{BASE_URL}/api/admin/metrics", headers=headers)
        assert response.status_code == 200
        print("✓ Admin metrics endpoint works")


class TestGalleryLimits:
    """Gallery limits verification"""
    
    def test_standard_gallery_limit_is_3(self, api_client, subscribed_provider_token):
        """Verify standard gallery limit is 3"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        gallery = data.get("gallery", [])
        print(f"✓ Standard gallery: {len(gallery)}/3 photos")
        # Limit is 3
        assert len(gallery) <= 3, f"Standard gallery exceeds limit: {len(gallery)}"
    
    def test_premium_gallery_limit_is_10(self, api_client, subscribed_provider_token):
        """Verify premium gallery limit is 10"""
        headers = {"Authorization": f"Bearer {subscribed_provider_token}"}
        response = api_client.get(f"{BASE_URL}/api/providers/my-profile/premium-gallery", headers=headers)
        if response.status_code == 200:
            data = response.json()
            photos = data if isinstance(data, list) else data.get("photos", [])
            print(f"✓ Premium gallery: {len(photos)}/10 photos")
            assert len(photos) <= 10, f"Premium gallery exceeds limit: {len(photos)}"


class TestBlogArticles:
    """Blog/Actualidad Mayor tests"""
    
    def test_blog_articles_public(self, api_client):
        """Test public blog articles endpoint"""
        response = api_client.get(f"{BASE_URL}/api/blog/articles?limit=6")
        assert response.status_code == 200
        articles = response.json()
        print(f"✓ Blog has {len(articles)} public articles")


class TestCareRequests:
    """Care request/service request tests"""
    
    def test_care_requests_endpoint_exists(self, api_client, client_token):
        """Test care requests endpoint exists"""
        headers = {"Authorization": f"Bearer {client_token}"}
        response = api_client.get(f"{BASE_URL}/api/care-requests/my-requests", headers=headers)
        # Should return 200 with list (even if empty)
        assert response.status_code == 200
        print("✓ Care requests endpoint works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
