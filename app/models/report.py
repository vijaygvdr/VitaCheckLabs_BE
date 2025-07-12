from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class ReportStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Report(Base):
    """Report model for managing lab test reports and results"""
    
    __tablename__ = "reports"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lab_test_id = Column(Integer, ForeignKey("lab_tests.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Report identification
    report_number = Column(String(50), unique=True, nullable=False, index=True)  # Unique report identifier
    
    # Report status and tracking
    status = Column(Enum(ReportStatus), default=ReportStatus.PENDING, nullable=False, index=True)
    
    # Test scheduling and execution
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # When test is scheduled
    collected_at = Column(DateTime(timezone=True), nullable=True)  # When sample was collected
    tested_at = Column(DateTime(timezone=True), nullable=True)    # When test was performed
    reviewed_at = Column(DateTime(timezone=True), nullable=True)  # When results were reviewed
    delivered_at = Column(DateTime(timezone=True), nullable=True) # When report was delivered
    
    # Sample and collection details
    sample_collected_by = Column(String(100), nullable=True)  # Technician/collector name
    collection_location = Column(String(200), nullable=True)  # Home/lab address
    collection_notes = Column(Text, nullable=True)            # Special collection notes
    
    # Test results
    results = Column(Text, nullable=True)  # JSON string with test results
    observations = Column(Text, nullable=True)  # Doctor's observations
    recommendations = Column(Text, nullable=True)  # Medical recommendations
    
    # File storage (S3)
    file_path = Column(String(500), nullable=True)  # S3 object key for PDF report
    file_original_name = Column(String(255), nullable=True)  # Original filename
    file_size = Column(Integer, nullable=True)  # File size in bytes
    file_type = Column(String(50), nullable=True)  # MIME type
    
    # Report visibility and sharing
    is_shared = Column(Boolean, default=False, nullable=False)
    shared_at = Column(DateTime(timezone=True), nullable=True)
    shared_with = Column(Text, nullable=True)  # JSON list of shared contacts
    
    # Quality control
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_by = Column(String(100), nullable=True)  # Verifying doctor/technician
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Billing and payment
    amount_charged = Column(Integer, nullable=True)  # Amount in paisa (for precision)
    payment_status = Column(String(20), default="pending", nullable=False)  # pending, paid, refunded
    payment_reference = Column(String(100), nullable=True)
    
    # Additional metadata
    notes = Column(Text, nullable=True)  # Internal notes
    priority = Column(String(20), default="normal", nullable=False)  # urgent, high, normal, low
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="reports")
    lab_test = relationship("LabTest", back_populates="reports")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_report_user_status', 'user_id', 'status'),
        Index('idx_report_user_created', 'user_id', 'created_at'),
        Index('idx_report_labtest_status', 'lab_test_id', 'status'),
        Index('idx_report_status_created', 'status', 'created_at'),
        Index('idx_report_scheduled_at', 'scheduled_at'),
        Index('idx_report_number', 'report_number'),
        Index('idx_report_payment_status', 'payment_status'),
    )
    
    def __repr__(self):
        return f"<Report(id={self.id}, report_number='{self.report_number}', user_id={self.user_id}, status='{self.status.value}')>"
    
    @property
    def amount_in_rupees(self):
        """Convert amount from paisa to rupees"""
        if self.amount_charged:
            return self.amount_charged / 100
        return 0
    
    def is_completed(self):
        """Check if report is completed"""
        return self.status in [ReportStatus.COMPLETED, ReportStatus.REVIEWED, ReportStatus.DELIVERED]
    
    def is_pending(self):
        """Check if report is still pending"""
        return self.status == ReportStatus.PENDING
    
    def can_be_downloaded(self):
        """Check if report can be downloaded"""
        return bool(self.file_path and self.status in [ReportStatus.COMPLETED, ReportStatus.REVIEWED, ReportStatus.DELIVERED])
    
    def get_turnaround_time(self):
        """Calculate turnaround time from collection to delivery"""
        if self.collected_at and self.delivered_at:
            return self.delivered_at - self.collected_at
        return None
    
    def update_status(self, new_status, notes=None):
        """Update report status with timestamp"""
        self.status = new_status
        now = func.now()
        
        if new_status == ReportStatus.COMPLETED:
            self.tested_at = now
        elif new_status == ReportStatus.REVIEWED:
            self.reviewed_at = now
        elif new_status == ReportStatus.DELIVERED:
            self.delivered_at = now
        
        if notes:
            self.notes = notes if not self.notes else f"{self.notes}\n{notes}"