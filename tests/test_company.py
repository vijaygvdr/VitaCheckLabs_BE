import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.company import Company, ContactMessage, MessageStatus
from app.core.security import get_password_hash
from datetime import datetime


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_company.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


class TestCompanyAPI:
    """Test suite for Company API endpoints"""
    
    def setup_method(self):
        """Set up test database and test data"""
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        
        # Create test admin user
        self.admin_user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("adminpass123"),
            full_name="Admin User",
            is_active=True,
            is_verified=True,
            role="admin"
        )
        self.db.add(self.admin_user)
        
        # Create test company
        self.test_company = Company(
            name="VitaCheck Labs",
            legal_name="VitaCheck Laboratories Pvt Ltd",
            description="Leading provider of diagnostic services",
            mission_statement="Providing accurate and timely diagnostic services",
            email="info@vitachecklabs.com",
            phone_primary="+91-9876543210",
            address_line1="123 Health Street",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            country="India",
            established_year=2020,
            services=["Blood Tests", "Urine Tests", "Imaging", "Home Collection"],
            specializations=["Cardiac Health", "Diabetes Care", "Preventive Health"],
            certifications=["NABL Accredited", "ISO 15189"],
            operating_hours={
                "monday": "09:00-18:00",
                "tuesday": "09:00-18:00",
                "wednesday": "09:00-18:00",
                "thursday": "09:00-18:00",
                "friday": "09:00-18:00",
                "saturday": "09:00-14:00",
                "sunday": "Closed"
            },
            is_active=True
        )
        self.db.add(self.test_company)
        
        self.db.commit()
        
        # Get admin authentication token
        admin_login_response = client.post("/api/v1/auth/login", data={
            "username": "admin@example.com",
            "password": "adminpass123"
        })
        self.admin_token = admin_login_response.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def teardown_method(self):
        """Clean up test database"""
        self.db.close()
        Base.metadata.drop_all(bind=engine)
    
    def test_get_company_info_public(self):
        """Test getting company information (public endpoint)"""
        response = client.get("/api/v1/company/info")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "VitaCheck Labs"
        assert data["description"] == "Leading provider of diagnostic services"
        assert data["established_year"] == 2020
        assert data["is_active"] == True
    
    def test_get_contact_info_public(self):
        """Test getting contact information (public endpoint)"""
        response = client.get("/api/v1/company/contact")
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "info@vitachecklabs.com"
        assert data["phone_primary"] == "+91-9876543210"
        assert data["city"] == "Mumbai"
        assert data["country"] == "India"
        assert "full_address" in data
    
    def test_get_services_public(self):
        """Test getting services list (public endpoint)"""
        response = client.get("/api/v1/company/services")
        
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "Blood Tests" in data["services"]
        assert "Urine Tests" in data["services"]
        assert data["total_services"] == 4
        assert "specializations" in data
        assert "certifications" in data
    
    def test_get_company_profile_public(self):
        """Test getting complete company profile (public endpoint)"""
        response = client.get("/api/v1/company/profile")
        
        assert response.status_code == 200
        data = response.json()
        assert "info" in data
        assert "contact" in data
        assert "services" in data
        assert "settings" in data
        
        # Verify nested data
        assert data["info"]["name"] == "VitaCheck Labs"
        assert data["contact"]["email"] == "info@vitachecklabs.com"
        assert len(data["services"]["services"]) == 4
        assert data["settings"]["accepts_home_collection"] == True
    
    def test_submit_contact_form_public(self):
        """Test submitting contact form (public endpoint)"""
        contact_data = {
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": "+91-9876543210",
            "subject": "Inquiry about blood tests",
            "message": "I would like to know more about comprehensive blood test packages.",
            "inquiry_type": "general",
            "source": "website"
        }
        
        response = client.post("/api/v1/company/contact", json=contact_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "Thank you for contacting us. We have received your message and will respond soon."
        assert "contact_id" in data
        assert "estimated_response_time" in data
        assert data["support_email"] == "info@vitachecklabs.com"
    
    def test_submit_contact_form_validation(self):
        """Test contact form validation"""
        # Test with missing required fields
        invalid_data = {
            "full_name": "J",  # Too short
            "email": "invalid-email",  # Invalid email
            "subject": "Hi",  # Too short
            "message": "Short"  # Too short
        }
        
        response = client.post("/api/v1/company/contact", json=invalid_data)
        assert response.status_code == 422
    
    def test_update_company_info_admin(self):
        """Test updating company information (admin only)"""
        update_data = {
            "description": "Updated description for leading diagnostic services",
            "mission_statement": "Updated mission to provide world-class healthcare",
            "tagline": "Your Health, Our Priority"
        }
        
        response = client.put(
            "/api/v1/company/info",
            json=update_data,
            headers=self.admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description for leading diagnostic services"
        assert data["mission_statement"] == "Updated mission to provide world-class healthcare"
        assert data["tagline"] == "Your Health, Our Priority"
    
    def test_update_company_info_unauthorized(self):
        """Test that unauthorized users cannot update company info"""
        update_data = {
            "description": "Unauthorized update attempt"
        }
        
        response = client.put("/api/v1/company/info", json=update_data)
        assert response.status_code == 401
    
    def test_get_contact_messages_admin(self):
        """Test getting contact messages list (admin only)"""
        # Create a test contact message first
        test_message = ContactMessage(
            full_name="Test User",
            email="test@example.com",
            subject="Test inquiry",
            message="This is a test message",
            inquiry_type="general"
        )
        self.db.add(test_message)
        self.db.commit()
        
        response = client.get("/api/v1/company/contact/messages", headers=self.admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert data["total"] >= 1
        assert len(data["messages"]) >= 1
        assert data["page"] == 1
    
    def test_get_contact_message_by_id_admin(self):
        """Test getting specific contact message (admin only)"""
        # Create a test contact message
        test_message = ContactMessage(
            full_name="Test User",
            email="test@example.com",
            subject="Test inquiry",
            message="This is a test message",
            inquiry_type="general",
            status=MessageStatus.NEW
        )
        self.db.add(test_message)
        self.db.commit()
        
        response = client.get(f"/api/v1/company/contact/messages/{test_message.id}", headers=self.admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_message.id
        assert data["full_name"] == "Test User"
        assert data["email"] == "test@example.com"
        assert data["status"] == "read"  # Should be marked as read
    
    def test_update_contact_message_admin(self):
        """Test updating contact message (admin only)"""
        # Create a test contact message
        test_message = ContactMessage(
            full_name="Test User",
            email="test@example.com",
            subject="Test inquiry",
            message="This is a test message",
            inquiry_type="support",
            status=MessageStatus.NEW
        )
        self.db.add(test_message)
        self.db.commit()
        
        update_data = {
            "status": "resolved",
            "response_message": "Thank you for your inquiry. We have resolved your issue.",
            "priority": "high"
        }
        
        response = client.put(
            f"/api/v1/company/contact/messages/{test_message.id}",
            json=update_data,
            headers=self.admin_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["response_message"] == "Thank you for your inquiry. We have resolved your issue."
        assert data["priority"] == "high"
        assert data["responded_at"] is not None
    
    def test_delete_contact_message_admin(self):
        """Test deleting contact message (admin only)"""
        # Create a test contact message
        test_message = ContactMessage(
            full_name="Test User",
            email="test@example.com",
            subject="Test inquiry",
            message="This is a test message",
            inquiry_type="general"
        )
        self.db.add(test_message)
        self.db.commit()
        
        response = client.delete(f"/api/v1/company/contact/messages/{test_message.id}", headers=self.admin_headers)
        
        assert response.status_code == 204
        
        # Verify message is deleted
        get_response = client.get(f"/api/v1/company/contact/messages/{test_message.id}", headers=self.admin_headers)
        assert get_response.status_code == 404
    
    def test_get_contact_stats_admin(self):
        """Test getting contact statistics (admin only)"""
        # Create multiple test messages with different statuses
        messages = [
            ContactMessage(
                full_name="User 1",
                email="user1@example.com",
                subject="New inquiry",
                message="New message",
                status=MessageStatus.NEW
            ),
            ContactMessage(
                full_name="User 2",
                email="user2@example.com",
                subject="Resolved inquiry",
                message="Resolved message",
                status=MessageStatus.RESOLVED,
                priority="high"
            ),
            ContactMessage(
                full_name="User 3",
                email="user3@example.com",
                subject="Urgent inquiry",
                message="Urgent message",
                priority="urgent"
            )
        ]
        
        for message in messages:
            self.db.add(message)
        self.db.commit()
        
        response = client.get("/api/v1/company/contact/stats", headers=self.admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data
        assert "new_messages" in data
        assert "pending_response" in data
        assert "resolved_messages" in data
        assert "urgent_messages" in data
        assert data["total_messages"] >= 3
        assert data["urgent_messages"] >= 1
    
    def test_filter_contact_messages_admin(self):
        """Test filtering contact messages (admin only)"""
        # Create messages with different types and statuses
        messages = [
            ContactMessage(
                full_name="Support User",
                email="support@example.com",
                subject="Support request",
                message="Need help",
                inquiry_type="support",
                status=MessageStatus.NEW
            ),
            ContactMessage(
                full_name="Feedback User",
                email="feedback@example.com",
                subject="Great service",
                message="Excellent experience",
                inquiry_type="feedback",
                status=MessageStatus.RESOLVED
            )
        ]
        
        for message in messages:
            self.db.add(message)
        self.db.commit()
        
        # Filter by inquiry type
        response = client.get("/api/v1/company/contact/messages?inquiry_type=support", headers=self.admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All returned messages should have support inquiry type
        for message in data["messages"]:
            assert message["inquiry_type"] == "support"
        
        # Filter by status
        response = client.get("/api/v1/company/contact/messages?status=resolved", headers=self.admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All returned messages should have resolved status
        for message in data["messages"]:
            assert message["status"] == "resolved"
    
    def test_search_contact_messages_admin(self):
        """Test searching contact messages (admin only)"""
        # Create a message with specific content
        test_message = ContactMessage(
            full_name="Searchable User",
            email="search@example.com",
            subject="Specific test subject",
            message="This message contains unique keywords for searching",
            inquiry_type="general"
        )
        self.db.add(test_message)
        self.db.commit()
        
        # Search for specific keywords
        response = client.get("/api/v1/company/contact/messages?search=unique keywords", headers=self.admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Should find the message with matching keywords
        assert data["total"] >= 1
        found = False
        for message in data["messages"]:
            if "unique keywords" in message["message"]:
                found = True
                break
        assert found
    
    def test_pagination_contact_messages_admin(self):
        """Test pagination of contact messages (admin only)"""
        response = client.get("/api/v1/company/contact/messages?page=1&per_page=5", headers=self.admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        assert data["page"] == 1
        assert data["per_page"] == 5
    
    def test_contact_messages_unauthorized(self):
        """Test that unauthorized users cannot access contact messages"""
        response = client.get("/api/v1/company/contact/messages")
        assert response.status_code == 401
    
    def test_company_info_not_found(self):
        """Test behavior when company info is not found"""
        # Delete the company record
        self.db.delete(self.test_company)
        self.db.commit()
        
        response = client.get("/api/v1/company/info")
        assert response.status_code == 404
        assert "Company information not found" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__])