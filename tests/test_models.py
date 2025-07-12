import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import User, UserRole, LabTest, Report, ReportStatus, Company

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


class TestUserModel:
    """Test cases for User model"""
    
    def test_user_creation(self, db_session):
        """Test basic user creation"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            first_name="Test",
            last_name="User",
            role=UserRole.USER
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.is_active == True
        assert user.is_verified == False
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_full_name_property(self, db_session):
        """Test user full_name property"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            first_name="John",
            last_name="Doe",
            role=UserRole.USER
        )
        assert user.full_name == "John Doe"
        
        # Test with only username
        user_no_name = User(
            username="testuser2",
            email="test2@example.com",
            password_hash="hashed_password",
            role=UserRole.USER
        )
        assert user_no_name.full_name == "testuser2"
    
    def test_user_role_methods(self, db_session):
        """Test user role checking methods"""
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password_hash="hashed_password",
            role=UserRole.ADMIN
        )
        assert admin_user.is_admin() == True
        assert admin_user.is_lab_technician() == False
        
        tech_user = User(
            username="tech",
            email="tech@example.com",
            password_hash="hashed_password",
            role=UserRole.LAB_TECHNICIAN
        )
        assert tech_user.is_admin() == False
        assert tech_user.is_lab_technician() == True
    
    def test_user_unique_constraints(self, db_session):
        """Test unique constraints on username and email"""
        user1 = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            role=UserRole.USER
        )
        db_session.add(user1)
        db_session.commit()
        
        # Try to create user with same username
        user2 = User(
            username="testuser",
            email="test2@example.com",
            password_hash="hashed_password",
            role=UserRole.USER
        )
        db_session.add(user2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestLabTestModel:
    """Test cases for LabTest model"""
    
    def test_lab_test_creation(self, db_session):
        """Test basic lab test creation"""
        lab_test = LabTest(
            name="Complete Blood Count",
            code="CBC",
            description="Measures different blood components",
            category="Blood Test",
            sub_category="Hematology",
            sample_type="Blood",
            price=Decimal("500.00"),
            duration_minutes=30,
            report_delivery_hours=24,
            is_active=True,
            is_home_collection_available=True
        )
        db_session.add(lab_test)
        db_session.commit()
        db_session.refresh(lab_test)
        
        assert lab_test.id is not None
        assert lab_test.name == "Complete Blood Count"
        assert lab_test.code == "CBC"
        assert lab_test.price == Decimal("500.00")
        assert lab_test.is_active == True
        assert lab_test.created_at is not None
    
    def test_lab_test_properties(self, db_session):
        """Test lab test properties and methods"""
        lab_test = LabTest(
            name="Liver Function Test",
            code="LFT",
            category="Blood Test",
            price=Decimal("800.50"),
            duration_minutes=45,
            report_delivery_hours=48,
            minimum_age=18,
            maximum_age=80
        )
        
        assert lab_test.display_name == "Liver Function Test (LFT)"
        assert lab_test.price_formatted == "₹800.50"
        assert lab_test.is_available_for_age(25) == True
        assert lab_test.is_available_for_age(15) == False
        assert lab_test.is_available_for_age(85) == False
        
        completion_time = lab_test.get_estimated_completion_time()
        assert completion_time == 45 + (48 * 60)  # 45 + 2880 = 2925 minutes
    
    def test_lab_test_unique_code(self, db_session):
        """Test unique constraint on test code"""
        test1 = LabTest(
            name="Test 1",
            code="TST001",
            category="Blood Test",
            price=Decimal("100.00")
        )
        db_session.add(test1)
        db_session.commit()
        
        test2 = LabTest(
            name="Test 2",
            code="TST001",  # Same code
            category="Urine Test",
            price=Decimal("150.00")
        )
        db_session.add(test2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db_session.commit()


class TestReportModel:
    """Test cases for Report model"""
    
    def test_report_creation(self, db_session):
        """Test basic report creation with relationships"""
        # Create user first
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            role=UserRole.USER
        )
        db_session.add(user)
        db_session.flush()
        
        # Create lab test
        lab_test = LabTest(
            name="Blood Sugar",
            code="BS",
            category="Blood Test",
            price=Decimal("200.00")
        )
        db_session.add(lab_test)
        db_session.flush()
        
        # Create report
        report = Report(
            user_id=user.id,
            lab_test_id=lab_test.id,
            report_number="RPT001",
            status=ReportStatus.PENDING,
            amount_charged=20000,  # 200.00 in paisa
            payment_status="pending",
            priority="normal"
        )
        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)
        
        assert report.id is not None
        assert report.user_id == user.id
        assert report.lab_test_id == lab_test.id
        assert report.status == ReportStatus.PENDING
        assert report.amount_in_rupees == 200.00
        assert report.created_at is not None
    
    def test_report_status_methods(self, db_session):
        """Test report status checking methods"""
        # Create dependencies
        user = User(username="test", email="test@example.com", password_hash="hash", role=UserRole.USER)
        lab_test = LabTest(name="Test", code="TST", category="Blood", price=Decimal("100"))
        db_session.add_all([user, lab_test])
        db_session.flush()
        
        report = Report(
            user_id=user.id,
            lab_test_id=lab_test.id,
            report_number="RPT002",
            status=ReportStatus.PENDING,
            payment_status="pending",
            priority="normal"
        )
        
        assert report.is_pending() == True
        assert report.is_completed() == False
        assert report.can_be_downloaded() == False
        
        # Update status
        report.status = ReportStatus.COMPLETED
        report.file_path = "s3://bucket/report.pdf"
        
        assert report.is_pending() == False
        assert report.is_completed() == True
        assert report.can_be_downloaded() == True
    
    def test_report_update_status_method(self, db_session):
        """Test report status update method with timestamps"""
        user = User(username="test", email="test@example.com", password_hash="hash", role=UserRole.USER)
        lab_test = LabTest(name="Test", code="TST", category="Blood", price=Decimal("100"))
        db_session.add_all([user, lab_test])
        db_session.flush()
        
        report = Report(
            user_id=user.id,
            lab_test_id=lab_test.id,
            report_number="RPT003",
            status=ReportStatus.PENDING,
            payment_status="pending",
            priority="normal"
        )
        db_session.add(report)
        db_session.commit()
        
        # Test status update
        report.update_status(ReportStatus.COMPLETED, "Test completed successfully")
        
        assert report.status == ReportStatus.COMPLETED
        assert "Test completed successfully" in (report.notes or "")


class TestCompanyModel:
    """Test cases for Company model"""
    
    def test_company_creation(self, db_session):
        """Test basic company creation"""
        company = Company(
            name="VitaCheck Labs",
            legal_name="VitaCheck Laboratories Pvt Ltd",
            email="info@vitacheck.com",
            phone_primary="+91-9876543210",
            address_line1="123 Medical Street",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            country="India",
            is_active=True,
            accepts_home_collection=True,
            home_collection_radius_km=25,
            minimum_order_amount=50000  # 500.00 in paisa
        )
        db_session.add(company)
        db_session.commit()
        db_session.refresh(company)
        
        assert company.id is not None
        assert company.name == "VitaCheck Labs"
        assert company.is_active == True
        assert company.country == "India"
        assert company.created_at is not None
    
    def test_company_properties_and_methods(self, db_session):
        """Test company properties and methods"""
        company = Company(
            name="Test Lab",
            address_line1="123 Main St",
            address_line2="Suite 456",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            country="India",
            email="test@lab.com",
            phone_primary="+91-1234567890",
            services=["Blood Test", "Urine Test"],
            accepts_home_collection=True,
            home_collection_radius_km=30
        )
        
        # Test full address
        expected_address = "123 Main St, Suite 456, Mumbai, Maharashtra, 400001, India"
        assert company.full_address == expected_address
        
        # Test primary contact
        contact = company.primary_contact
        assert contact["email"] == "test@lab.com"
        assert contact["phone"] == "+91-1234567890"
        
        # Test service methods
        assert company.get_service_list() == ["Blood Test", "Urine Test"]
        
        company.add_service("X-Ray")
        assert "X-Ray" in company.get_service_list()
        
        company.remove_service("Blood Test")
        assert "Blood Test" not in company.get_service_list()
        
        # Test service area
        assert company.is_within_service_area(25) == True
        assert company.is_within_service_area(35) == False
    
    def test_company_operating_hours(self, db_session):
        """Test company operating hours functionality"""
        operating_hours = {
            "monday": {"open": "09:00", "close": "18:00"},
            "tuesday": {"open": "09:00", "close": "18:00"},
            "saturday": {"open": "09:00", "close": "14:00"},
            "sunday": "closed"
        }
        
        company = Company(
            name="Test Lab",
            operating_hours=operating_hours
        )
        
        # Test getting hours for specific days (0=Monday, 6=Sunday)
        monday_hours = company.get_operating_hours_today(0)
        assert monday_hours == {"open": "09:00", "close": "18:00"}
        
        sunday_hours = company.get_operating_hours_today(6)
        assert sunday_hours == "closed"


class TestModelRelationships:
    """Test model relationships"""
    
    def test_user_report_relationship(self, db_session):
        """Test User-Report relationship"""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            role=UserRole.USER
        )
        lab_test = LabTest(
            name="Test",
            code="TST",
            category="Blood",
            price=Decimal("100")
        )
        db_session.add_all([user, lab_test])
        db_session.flush()
        
        report1 = Report(
            user_id=user.id,
            lab_test_id=lab_test.id,
            report_number="RPT001",
            status=ReportStatus.PENDING,
            payment_status="pending",
            priority="normal"
        )
        report2 = Report(
            user_id=user.id,
            lab_test_id=lab_test.id,
            report_number="RPT002",
            status=ReportStatus.COMPLETED,
            payment_status="paid",
            priority="normal"
        )
        db_session.add_all([report1, report2])
        db_session.commit()
        
        # Test relationship
        assert len(user.reports) == 2
        assert report1.user == user
        assert report2.user == user
    
    def test_lab_test_report_relationship(self, db_session):
        """Test LabTest-Report relationship"""
        user = User(username="test", email="test@example.com", password_hash="hash", role=UserRole.USER)
        lab_test = LabTest(name="CBC", code="CBC", category="Blood", price=Decimal("500"))
        db_session.add_all([user, lab_test])
        db_session.flush()
        
        report = Report(
            user_id=user.id,
            lab_test_id=lab_test.id,
            report_number="RPT001",
            status=ReportStatus.PENDING,
            payment_status="pending",
            priority="normal"
        )
        db_session.add(report)
        db_session.commit()
        
        # Test relationship
        assert len(lab_test.reports) == 1
        assert report.lab_test == lab_test


if __name__ == "__main__":
    pytest.main([__file__])