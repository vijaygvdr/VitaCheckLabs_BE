import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.lab_test import LabTest
from app.models.report import Report, ReportStatus
from app.core.security import get_password_hash
from datetime import datetime


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_reports.db"
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


class TestReportsAPI:
    """Test suite for Reports API endpoints"""
    
    def setup_method(self):
        """Set up test database and test data"""
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()
        
        # Create test user
        self.test_user = User(
            email="test@example.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="Test User",
            is_active=True,
            is_verified=True
        )
        self.db.add(self.test_user)
        
        # Create admin user
        self.admin_user = User(
            email="admin@example.com",
            hashed_password=get_password_hash("adminpass123"),
            full_name="Admin User",
            is_active=True,
            is_verified=True,
            role="admin"
        )
        self.db.add(self.admin_user)
        
        # Create test lab test
        self.test_lab_test = LabTest(
            name="Complete Blood Count",
            code="CBC001",
            description="Comprehensive blood analysis",
            category="Blood Test",
            price=500.00,
            is_active=True
        )
        self.db.add(self.test_lab_test)
        
        self.db.commit()
        
        # Get authentication tokens
        login_response = client.post("/api/v1/auth/login", data={
            "username": "test@example.com",
            "password": "testpass123"
        })
        self.user_token = login_response.json()["access_token"]
        
        admin_login_response = client.post("/api/v1/auth/login", data={
            "username": "admin@example.com",
            "password": "adminpass123"
        })
        self.admin_token = admin_login_response.json()["access_token"]
        
        self.user_headers = {"Authorization": f"Bearer {self.user_token}"}
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
    
    def teardown_method(self):
        """Clean up test database"""
        self.db.close()
        Base.metadata.drop_all(bind=engine)
    
    def test_create_report(self):
        """Test creating a new report"""
        report_data = {
            "lab_test_id": self.test_lab_test.id,
            "priority": "normal",
            "collection_location": "Home",
            "collection_notes": "Morning collection preferred"
        }
        
        response = client.post(
            "/api/v1/reports/",
            json=report_data,
            headers=self.user_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["lab_test_id"] == self.test_lab_test.id
        assert data["priority"] == "normal"
        assert data["status"] == "pending"
        assert "report_number" in data
    
    def test_get_reports_list(self):
        """Test getting list of reports"""
        # Create a test report first
        test_report = Report(
            user_id=self.test_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010001",
            status=ReportStatus.PENDING
        )
        self.db.add(test_report)
        self.db.commit()
        
        response = client.get("/api/v1/reports/", headers=self.user_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert data["total"] >= 1
        assert len(data["reports"]) >= 1
    
    def test_get_report_by_id(self):
        """Test getting a specific report by ID"""
        # Create a test report
        test_report = Report(
            user_id=self.test_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010002",
            status=ReportStatus.PENDING
        )
        self.db.add(test_report)
        self.db.commit()
        
        response = client.get(f"/api/v1/reports/{test_report.id}", headers=self.user_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_report.id
        assert data["report_number"] == "RPT202401010002"
    
    def test_update_report(self):
        """Test updating a report"""
        # Create a test report
        test_report = Report(
            user_id=self.test_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010003",
            status=ReportStatus.PENDING
        )
        self.db.add(test_report)
        self.db.commit()
        
        update_data = {
            "collection_notes": "Updated collection notes",
            "priority": "high"
        }
        
        response = client.put(
            f"/api/v1/reports/{test_report.id}",
            json=update_data,
            headers=self.user_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["collection_notes"] == "Updated collection notes"
        assert data["priority"] == "high"
    
    def test_delete_report(self):
        """Test deleting a report"""
        # Create a test report
        test_report = Report(
            user_id=self.test_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010004",
            status=ReportStatus.PENDING
        )
        self.db.add(test_report)
        self.db.commit()
        
        response = client.delete(f"/api/v1/reports/{test_report.id}", headers=self.user_headers)
        
        assert response.status_code == 204
        
        # Verify report is deleted
        get_response = client.get(f"/api/v1/reports/{test_report.id}", headers=self.user_headers)
        assert get_response.status_code == 404
    
    def test_get_report_stats(self):
        """Test getting report statistics"""
        response = client.get("/api/v1/reports/stats/overview", headers=self.user_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_reports" in data
        assert "pending_reports" in data
        assert "completed_reports" in data
        assert "total_revenue" in data
    
    def test_unauthorized_access(self):
        """Test that unauthorized users cannot access reports"""
        response = client.get("/api/v1/reports/")
        assert response.status_code == 401
    
    def test_user_cannot_access_other_users_reports(self):
        """Test that users cannot access reports from other users"""
        # Create another user
        other_user = User(
            email="other@example.com",
            hashed_password=get_password_hash("otherpass123"),
            full_name="Other User",
            is_active=True,
            is_verified=True
        )
        self.db.add(other_user)
        self.db.commit()
        
        # Create a report for the other user
        other_report = Report(
            user_id=other_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010005",
            status=ReportStatus.PENDING
        )
        self.db.add(other_report)
        self.db.commit()
        
        # Try to access other user's report
        response = client.get(f"/api/v1/reports/{other_report.id}", headers=self.user_headers)
        assert response.status_code == 404
    
    def test_admin_can_access_all_reports(self):
        """Test that admin users can access all reports"""
        # Create a report for regular user
        test_report = Report(
            user_id=self.test_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010006",
            status=ReportStatus.PENDING
        )
        self.db.add(test_report)
        self.db.commit()
        
        # Admin should be able to access any report
        response = client.get(f"/api/v1/reports/{test_report.id}", headers=self.admin_headers)
        assert response.status_code == 200
    
    def test_filter_reports_by_status(self):
        """Test filtering reports by status"""
        # Create reports with different statuses
        pending_report = Report(
            user_id=self.test_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010007",
            status=ReportStatus.PENDING
        )
        completed_report = Report(
            user_id=self.test_user.id,
            lab_test_id=self.test_lab_test.id,
            report_number="RPT202401010008",
            status=ReportStatus.COMPLETED
        )
        self.db.add_all([pending_report, completed_report])
        self.db.commit()
        
        # Filter by pending status
        response = client.get("/api/v1/reports/?status=pending", headers=self.user_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All returned reports should have pending status
        for report in data["reports"]:
            assert report["status"] == "pending"
    
    def test_pagination(self):
        """Test pagination of reports list"""
        response = client.get("/api/v1/reports/?page=1&per_page=10", headers=self.user_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        assert data["page"] == 1
        assert data["per_page"] == 10


if __name__ == "__main__":
    pytest.main([__file__])