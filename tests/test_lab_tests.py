import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.main import app
from app.database import get_db, Base
from app.models.user import User, UserRole
from app.models.lab_test import LabTest
from app.core.security import create_access_token, get_password_hash
from app.core.config import settings

# Test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_lab_tests.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def create_test_user(db: Session, username: str, email: str, password: str, role: UserRole = UserRole.USER) -> User:
    """Helper function to create test user"""
    password_hash = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        password_hash=password_hash,
        role=role,
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session"""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    
    yield session
    
    # Cleanup
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def admin_user(db_session):
    """Create admin user for testing"""
    return create_test_user(
        db_session,
        username="admin",
        email="admin@test.com",
        password="testpass123",
        role=UserRole.ADMIN
    )


@pytest.fixture
def regular_user(db_session):
    """Create regular user for testing"""
    return create_test_user(
        db_session,
        username="user",
        email="user@test.com",
        password="testpass123",
        role=UserRole.USER
    )


@pytest.fixture
def admin_token(admin_user):
    """Create admin access token"""
    return create_access_token(data={"sub": str(admin_user.id)})


@pytest.fixture
def user_token(regular_user):
    """Create user access token"""
    return create_access_token(data={"sub": str(regular_user.id)})


@pytest.fixture
def sample_lab_test(db_session):
    """Create a sample lab test"""
    lab_test = LabTest(
        name="Complete Blood Count",
        code="CBC",
        description="A complete blood count test",
        category="Blood Test",
        sub_category="Hematology",
        sample_type="Blood",
        requirements="12 hours fasting required",
        procedure="Blood sample collection",
        price=Decimal("500.00"),
        duration_minutes=30,
        report_delivery_hours=24,
        is_active=True,
        is_home_collection_available=True,
        minimum_age=1,
        maximum_age=100,
        reference_ranges='{"hemoglobin": "12-16 g/dL"}',
        units="g/dL"
    )
    db_session.add(lab_test)
    db_session.commit()
    db_session.refresh(lab_test)
    return lab_test


class TestLabTestsPublicEndpoints:
    """Test public lab tests endpoints (no authentication required)"""
    
    def test_get_lab_tests_list_success(self, db_session, sample_lab_test):
        """Test getting lab tests list without authentication"""
        response = client.get("/api/v1/lab-tests/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tests" in data
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "total_pages" in data
        
        assert data["total"] == 1
        assert len(data["tests"]) == 1
        assert data["tests"][0]["name"] == "Complete Blood Count"
        assert data["tests"][0]["code"] == "CBC"
    
    def test_get_lab_tests_with_filters(self, db_session, sample_lab_test):
        """Test getting lab tests with filters"""
        # Test category filter
        response = client.get("/api/v1/lab-tests/?category=Blood%20Test")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        
        # Test price filter
        response = client.get("/api/v1/lab-tests/?min_price=400&max_price=600")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        
        # Test search
        response = client.get("/api/v1/lab-tests/?search=blood")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
    
    def test_get_lab_tests_pagination(self, db_session):
        """Test pagination"""
        # Create multiple lab tests
        for i in range(5):
            lab_test = LabTest(
                name=f"Test {i}",
                code=f"TEST{i}",
                category="Blood Test",
                price=Decimal("100.00"),
                is_active=True
            )
            db_session.add(lab_test)
        db_session.commit()
        
        # Test first page
        response = client.get("/api/v1/lab-tests/?page=1&per_page=3")
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 1
        assert data["per_page"] == 3
        assert len(data["tests"]) == 3
        assert data["total"] == 5
        assert data["total_pages"] == 2
    
    def test_get_lab_test_by_id_success(self, db_session, sample_lab_test):
        """Test getting specific lab test by ID"""
        response = client.get(f"/api/v1/lab-tests/{sample_lab_test.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == sample_lab_test.id
        assert data["name"] == "Complete Blood Count"
        assert data["code"] == "CBC"
        assert data["price"] == "500.00"
    
    def test_get_lab_test_by_id_not_found(self, db_session):
        """Test getting non-existent lab test"""
        response = client.get("/api/v1/lab-tests/999")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_get_categories_list(self, db_session, sample_lab_test):
        """Test getting categories list"""
        response = client.get("/api/v1/lab-tests/categories/list")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        assert data[0]["category"] == "Blood Test"
        assert data[0]["count"] == 1
        assert "Hematology" in data[0]["sub_categories"]


class TestLabTestsAdminEndpoints:
    """Test admin-only lab tests endpoints"""
    
    def test_create_lab_test_success(self, db_session, admin_token):
        """Test creating lab test as admin"""
        test_data = {
            "name": "Liver Function Test",
            "code": "LFT",
            "description": "Liver function test",
            "category": "Blood Test",
            "sub_category": "Biochemistry",
            "sample_type": "Blood",
            "price": "750.50",
            "duration_minutes": 45,
            "report_delivery_hours": 48,
            "is_active": True,
            "is_home_collection_available": False
        }
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.post("/api/v1/lab-tests/", json=test_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["name"] == "Liver Function Test"
        assert data["code"] == "LFT"
        assert data["price"] == "750.50"
    
    def test_create_lab_test_duplicate_code(self, db_session, admin_token, sample_lab_test):
        """Test creating lab test with duplicate code"""
        test_data = {
            "name": "Another CBC",
            "code": "CBC",  # Duplicate code
            "category": "Blood Test",
            "price": "600.00"
        }
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.post("/api/v1/lab-tests/", json=test_data, headers=headers)
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()
    
    def test_create_lab_test_unauthorized(self, db_session, user_token):
        """Test creating lab test as regular user (should fail)"""
        test_data = {
            "name": "Test",
            "code": "TEST",
            "category": "Blood Test",
            "price": "100.00"
        }
        
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.post("/api/v1/lab-tests/", json=test_data, headers=headers)
        
        assert response.status_code == 403
    
    def test_update_lab_test_success(self, db_session, admin_token, sample_lab_test):
        """Test updating lab test as admin"""
        update_data = {
            "name": "Updated CBC Test",
            "price": "600.00",
            "is_active": False
        }
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put(f"/api/v1/lab-tests/{sample_lab_test.id}", json=update_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "Updated CBC Test"
        assert data["price"] == "600.00"
        assert data["is_active"] == False
    
    def test_update_lab_test_not_found(self, db_session, admin_token):
        """Test updating non-existent lab test"""
        update_data = {"name": "Updated Test"}
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.put("/api/v1/lab-tests/999", json=update_data, headers=headers)
        
        assert response.status_code == 404
    
    def test_update_lab_test_unauthorized(self, db_session, user_token, sample_lab_test):
        """Test updating lab test as regular user (should fail)"""
        update_data = {"name": "Updated Test"}
        
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.put(f"/api/v1/lab-tests/{sample_lab_test.id}", json=update_data, headers=headers)
        
        assert response.status_code == 403
    
    def test_delete_lab_test_success(self, db_session, admin_token, sample_lab_test):
        """Test deleting lab test as admin"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete(f"/api/v1/lab-tests/{sample_lab_test.id}", headers=headers)
        
        assert response.status_code == 204
        
        # Verify test is deleted
        get_response = client.get(f"/api/v1/lab-tests/{sample_lab_test.id}")
        assert get_response.status_code == 404
    
    def test_delete_lab_test_not_found(self, db_session, admin_token):
        """Test deleting non-existent lab test"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.delete("/api/v1/lab-tests/999", headers=headers)
        
        assert response.status_code == 404
    
    def test_delete_lab_test_unauthorized(self, db_session, user_token, sample_lab_test):
        """Test deleting lab test as regular user (should fail)"""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.delete(f"/api/v1/lab-tests/{sample_lab_test.id}", headers=headers)
        
        assert response.status_code == 403
    
    def test_get_lab_test_stats(self, db_session, admin_token, sample_lab_test):
        """Test getting lab test statistics"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.get("/api/v1/lab-tests/stats/overview", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_tests" in data
        assert "active_tests" in data
        assert "categories_count" in data
        assert "average_price" in data
        assert "most_popular_category" in data
        assert "home_collection_available" in data
        
        assert data["total_tests"] == 1
        assert data["active_tests"] == 1
    
    def test_get_lab_test_stats_unauthorized(self, db_session, user_token):
        """Test getting stats as regular user (should fail)"""
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.get("/api/v1/lab-tests/stats/overview", headers=headers)
        
        assert response.status_code == 403


class TestLabTestBooking:
    """Test lab test booking functionality"""
    
    def test_book_lab_test_success(self, db_session, user_token, sample_lab_test):
        """Test booking lab test successfully"""
        future_date = datetime.now() + timedelta(days=1)
        booking_data = {
            "test_id": sample_lab_test.id,
            "patient_name": "John Doe",
            "patient_age": 30,
            "patient_gender": "Male",
            "appointment_date": future_date.isoformat(),
            "home_collection": True,
            "address": "123 Main St",
            "phone_number": "1234567890",
            "special_instructions": "Please call before arrival"
        }
        
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.post(f"/api/v1/lab-tests/{sample_lab_test.id}/book", json=booking_data, headers=headers)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["patient_name"] == "John Doe"
        assert data["patient_age"] == 30
        assert data["home_collection"] == True
        assert data["booking_status"] == "confirmed"
    
    def test_book_lab_test_age_restriction(self, db_session, user_token):
        """Test booking lab test with age restrictions"""
        # Create test with age restrictions
        restricted_test = LabTest(
            name="Pediatric Test",
            code="PED",
            category="Blood Test",
            price=Decimal("300.00"),
            is_active=True,
            minimum_age=5,
            maximum_age=18
        )
        db_session.add(restricted_test)
        db_session.commit()
        db_session.refresh(restricted_test)
        
        future_date = datetime.now() + timedelta(days=1)
        booking_data = {
            "test_id": restricted_test.id,
            "patient_name": "John Doe",
            "patient_age": 25,  # Outside age range
            "patient_gender": "Male",
            "appointment_date": future_date.isoformat(),
            "phone_number": "1234567890"
        }
        
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.post(f"/api/v1/lab-tests/{restricted_test.id}/book", json=booking_data, headers=headers)
        
        assert response.status_code == 400
        assert "age requirements" in response.json()["detail"].lower()
    
    def test_book_lab_test_home_collection_not_available(self, db_session, user_token):
        """Test booking with home collection when not available"""
        # Create test without home collection
        no_home_test = LabTest(
            name="Lab Only Test",
            code="LAB",
            category="Blood Test",
            price=Decimal("400.00"),
            is_active=True,
            is_home_collection_available=False
        )
        db_session.add(no_home_test)
        db_session.commit()
        db_session.refresh(no_home_test)
        
        future_date = datetime.now() + timedelta(days=1)
        booking_data = {
            "test_id": no_home_test.id,
            "patient_name": "John Doe",
            "patient_age": 30,
            "patient_gender": "Male",
            "appointment_date": future_date.isoformat(),
            "home_collection": True,  # Not available
            "phone_number": "1234567890"
        }
        
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.post(f"/api/v1/lab-tests/{no_home_test.id}/book", json=booking_data, headers=headers)
        
        assert response.status_code == 400
        assert "home collection" in response.json()["detail"].lower()
    
    def test_book_lab_test_invalid_date(self, db_session, user_token, sample_lab_test):
        """Test booking with past date"""
        past_date = datetime.now() - timedelta(days=1)
        booking_data = {
            "test_id": sample_lab_test.id,
            "patient_name": "John Doe",
            "patient_age": 30,
            "patient_gender": "Male",
            "appointment_date": past_date.isoformat(),
            "phone_number": "1234567890"
        }
        
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.post(f"/api/v1/lab-tests/{sample_lab_test.id}/book", json=booking_data, headers=headers)
        
        assert response.status_code == 422  # Validation error
    
    def test_book_lab_test_unauthorized(self, db_session, sample_lab_test):
        """Test booking without authentication"""
        future_date = datetime.now() + timedelta(days=1)
        booking_data = {
            "test_id": sample_lab_test.id,
            "patient_name": "John Doe",
            "patient_age": 30,
            "patient_gender": "Male",
            "appointment_date": future_date.isoformat(),
            "phone_number": "1234567890"
        }
        
        response = client.post(f"/api/v1/lab-tests/{sample_lab_test.id}/book", json=booking_data)
        
        assert response.status_code == 401
    
    def test_book_inactive_lab_test(self, db_session, user_token):
        """Test booking inactive lab test"""
        inactive_test = LabTest(
            name="Inactive Test",
            code="INACTIVE",
            category="Blood Test",
            price=Decimal("200.00"),
            is_active=False
        )
        db_session.add(inactive_test)
        db_session.commit()
        db_session.refresh(inactive_test)
        
        future_date = datetime.now() + timedelta(days=1)
        booking_data = {
            "test_id": inactive_test.id,
            "patient_name": "John Doe",
            "patient_age": 30,
            "patient_gender": "Male",
            "appointment_date": future_date.isoformat(),
            "phone_number": "1234567890"
        }
        
        headers = {"Authorization": f"Bearer {user_token}"}
        response = client.post(f"/api/v1/lab-tests/{inactive_test.id}/book", json=booking_data, headers=headers)
        
        assert response.status_code == 404


class TestLabTestValidation:
    """Test lab test data validation"""
    
    def test_create_lab_test_invalid_price(self, db_session, admin_token):
        """Test creating lab test with invalid price"""
        test_data = {
            "name": "Test",
            "code": "TEST",
            "category": "Blood Test",
            "price": -100.00  # Invalid negative price
        }
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.post("/api/v1/lab-tests/", json=test_data, headers=headers)
        
        assert response.status_code == 422
    
    def test_create_lab_test_invalid_age_range(self, db_session, admin_token):
        """Test creating lab test with invalid age range"""
        test_data = {
            "name": "Test",
            "code": "TEST",
            "category": "Blood Test",
            "price": "100.00",
            "minimum_age": 50,
            "maximum_age": 30  # Max less than min
        }
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = client.post("/api/v1/lab-tests/", json=test_data, headers=headers)
        
        assert response.status_code == 422