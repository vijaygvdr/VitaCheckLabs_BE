# Import all models to ensure they are registered with SQLAlchemy
from .user import User, UserRole
from .lab_test import LabTest
from .report import Report, ReportStatus
from .company import Company
from .booking import Booking, BookingStatus

# Export all models for easy importing
__all__ = [
    "User",
    "UserRole", 
    "LabTest",
    "Report",
    "ReportStatus",
    "Company",
    "Booking",
    "BookingStatus"
]