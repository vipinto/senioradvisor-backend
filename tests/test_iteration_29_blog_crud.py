"""
Iteration 29: Blog Admin Panel CRUD Testing
Tests for blog articles CRUD operations:
- GET /api/blog/articles - List all articles
- POST /api/blog/articles - Create new article
- GET /api/blog/articles/{slug} - Get article by slug
- PUT /api/blog/articles/{article_id} - Update article
- DELETE /api/blog/articles/{article_id} - Delete article
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@senioradvisor.cl"
ADMIN_PASSWORD = "admin123"

class TestBlogCRUD:
    """Blog articles CRUD endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        if login_response.status_code == 200:
            self.admin_token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.admin_token}"})
            self.admin_logged_in = True
        else:
            self.admin_logged_in = False
            self.admin_token = None
    
    # ===== GET /api/blog/articles =====
    
    def test_get_articles_returns_list(self):
        """Test GET /api/blog/articles returns list of articles"""
        response = self.session.get(f"{BASE_URL}/api/blog/articles")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list of articles"
        
        # Should have seed articles
        print(f"Found {len(data)} articles")
    
    def test_get_articles_sorted_newest_first(self):
        """Test articles are sorted by created_at descending (newest first)"""
        response = self.session.get(f"{BASE_URL}/api/blog/articles")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) >= 2:
            # Check that articles are sorted newest first
            dates = [a.get('created_at', '') for a in data]
            assert dates == sorted(dates, reverse=True), "Articles should be sorted newest first"
            print("Articles are correctly sorted newest first")
    
    def test_get_articles_with_published_only_false(self):
        """Test GET /api/blog/articles?published_only=false returns all articles including unpublished"""
        response = self.session.get(f"{BASE_URL}/api/blog/articles?published_only=false")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Found {len(data)} articles (including unpublished)")
    
    def test_article_structure(self):
        """Test articles have required fields"""
        response = self.session.get(f"{BASE_URL}/api/blog/articles")
        assert response.status_code == 200
        
        data = response.json()
        if len(data) > 0:
            article = data[0]
            required_fields = ['article_id', 'slug', 'title', 'excerpt', 'content', 'image', 'published', 'created_at']
            
            for field in required_fields:
                assert field in article, f"Article missing required field: {field}"
            
            print(f"Article structure verified: {list(article.keys())}")
    
    # ===== GET /api/blog/articles/{slug} =====
    
    def test_get_article_by_slug(self):
        """Test GET /api/blog/articles/{slug} returns single article"""
        # First get list to find a valid slug
        list_response = self.session.get(f"{BASE_URL}/api/blog/articles")
        assert list_response.status_code == 200
        
        articles = list_response.json()
        if len(articles) > 0:
            slug = articles[0]['slug']
            
            response = self.session.get(f"{BASE_URL}/api/blog/articles/{slug}")
            assert response.status_code == 200
            
            article = response.json()
            assert article['slug'] == slug
            print(f"Successfully retrieved article by slug: {slug}")
    
    def test_get_article_by_slug_not_found(self):
        """Test GET /api/blog/articles/{slug} returns 404 for invalid slug"""
        response = self.session.get(f"{BASE_URL}/api/blog/articles/invalid-slug-that-does-not-exist-12345")
        
        assert response.status_code == 404
        print("404 returned for invalid slug as expected")
    
    # ===== POST /api/blog/articles =====
    
    def test_create_article(self):
        """Test POST /api/blog/articles creates new article"""
        unique_id = str(uuid.uuid4())[:6]
        
        article_data = {
            "title": f"TEST_Article {unique_id}",
            "excerpt": f"Test excerpt for article {unique_id}",
            "content": "This is test content.\n\nWith multiple paragraphs.",
            "image": "https://picsum.photos/800/600"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/blog/articles",
            json=article_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        created = response.json()
        assert 'article_id' in created, "Created article should have article_id"
        assert 'slug' in created, "Created article should have slug"
        assert created['title'] == article_data['title']
        assert created['published'] == True, "New articles should be published by default"
        
        # Store for cleanup
        self.created_article_id = created['article_id']
        self.created_slug = created['slug']
        
        print(f"Created article: {created['article_id']} with slug: {created['slug']}")
        
        # Verify via GET
        verify_response = self.session.get(f"{BASE_URL}/api/blog/articles/{created['slug']}")
        assert verify_response.status_code == 200
        verified = verify_response.json()
        assert verified['title'] == article_data['title']
        
        # Cleanup - delete the test article
        delete_response = self.session.delete(f"{BASE_URL}/api/blog/articles/{created['article_id']}")
        assert delete_response.status_code == 200
        print(f"Cleaned up test article: {created['article_id']}")
    
    def test_create_article_generates_slug(self):
        """Test slug is auto-generated from title"""
        unique_id = str(uuid.uuid4())[:6]
        
        article_data = {
            "title": f"TEST Mi Artículo Con Acentos {unique_id}",
            "excerpt": "Test excerpt",
            "content": "Test content",
            "image": "https://picsum.photos/800/600"
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/blog/articles",
            json=article_data
        )
        
        assert response.status_code == 200
        created = response.json()
        
        # Slug should be lowercase, no accents, dashes for spaces
        assert "á" not in created['slug'], "Slug should not contain accents"
        assert " " not in created['slug'], "Slug should not contain spaces"
        print(f"Generated slug: {created['slug']}")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/blog/articles/{created['article_id']}")
    
    # ===== PUT /api/blog/articles/{article_id} =====
    
    def test_update_article(self):
        """Test PUT /api/blog/articles/{article_id} updates article"""
        unique_id = str(uuid.uuid4())[:6]
        
        # First create an article
        article_data = {
            "title": f"TEST_Original Title {unique_id}",
            "excerpt": "Original excerpt",
            "content": "Original content",
            "image": "https://picsum.photos/800/600"
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/blog/articles",
            json=article_data
        )
        assert create_response.status_code == 200
        created = create_response.json()
        article_id = created['article_id']
        
        # Update the article
        update_data = {
            "title": f"TEST_Updated Title {unique_id}",
            "excerpt": "Updated excerpt"
        }
        
        update_response = self.session.put(
            f"{BASE_URL}/api/blog/articles/{article_id}",
            json=update_data
        )
        
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        updated = update_response.json()
        assert updated['title'] == update_data['title']
        assert updated['excerpt'] == update_data['excerpt']
        # Content should remain unchanged
        assert updated['content'] == article_data['content']
        
        print(f"Updated article {article_id}: title changed to '{updated['title']}'")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/blog/articles/{article_id}")
    
    def test_update_article_not_found(self):
        """Test PUT /api/blog/articles/{article_id} returns 404 for invalid ID"""
        update_data = {"title": "Test"}
        
        response = self.session.put(
            f"{BASE_URL}/api/blog/articles/invalid-article-id-12345",
            json=update_data
        )
        
        assert response.status_code == 404
        print("404 returned for invalid article_id as expected")
    
    def test_update_article_toggle_published(self):
        """Test updating published status of article"""
        unique_id = str(uuid.uuid4())[:6]
        
        # Create article (published by default)
        create_response = self.session.post(
            f"{BASE_URL}/api/blog/articles",
            json={
                "title": f"TEST_Toggle Published {unique_id}",
                "excerpt": "Test",
                "content": "Test",
                "image": "https://picsum.photos/800/600"
            }
        )
        assert create_response.status_code == 200
        created = create_response.json()
        article_id = created['article_id']
        
        assert created['published'] == True
        
        # Toggle to unpublished
        update_response = self.session.put(
            f"{BASE_URL}/api/blog/articles/{article_id}",
            json={"published": False}
        )
        
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated['published'] == False
        
        print(f"Toggled article {article_id} to unpublished")
        
        # Cleanup
        self.session.delete(f"{BASE_URL}/api/blog/articles/{article_id}")
    
    # ===== DELETE /api/blog/articles/{article_id} =====
    
    def test_delete_article(self):
        """Test DELETE /api/blog/articles/{article_id} removes article"""
        unique_id = str(uuid.uuid4())[:6]
        
        # Create article
        create_response = self.session.post(
            f"{BASE_URL}/api/blog/articles",
            json={
                "title": f"TEST_To Be Deleted {unique_id}",
                "excerpt": "Test",
                "content": "Test",
                "image": "https://picsum.photos/800/600"
            }
        )
        assert create_response.status_code == 200
        created = create_response.json()
        article_id = created['article_id']
        slug = created['slug']
        
        # Delete article
        delete_response = self.session.delete(f"{BASE_URL}/api/blog/articles/{article_id}")
        
        assert delete_response.status_code == 200
        assert delete_response.json()['status'] == 'deleted'
        
        print(f"Deleted article {article_id}")
        
        # Verify deletion
        get_response = self.session.get(f"{BASE_URL}/api/blog/articles/{slug}")
        assert get_response.status_code == 404, "Deleted article should return 404"
        
        print("Verified article no longer exists")
    
    def test_delete_article_not_found(self):
        """Test DELETE /api/blog/articles/{article_id} returns 404 for invalid ID"""
        response = self.session.delete(f"{BASE_URL}/api/blog/articles/invalid-article-id-12345")
        
        assert response.status_code == 404
        print("404 returned for invalid article_id on delete as expected")


class TestAdminAuth:
    """Test admin authentication"""
    
    def test_admin_login(self):
        """Test admin login works with correct credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        assert response.status_code == 200, f"Admin login failed: {response.status_code} - {response.text}"
        
        data = response.json()
        assert 'token' in data
        assert 'user' in data
        assert data['user']['role'] == 'admin'
        
        print(f"Admin login successful. User: {data['user']['email']}, Role: {data['user']['role']}")
    
    def test_admin_can_access_admin_endpoints(self):
        """Test admin can access admin-only endpoints"""
        # Login
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_response.status_code == 200
        token = login_response.json()['token']
        
        # Access admin stats
        stats_response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert stats_response.status_code == 200
        print("Admin can access /api/admin/stats endpoint")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
