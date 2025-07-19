from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum
import uuid


class BookingStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Booking(Base):
    """Booking model for managing lab test appointments"""
    
    __tablename__ = "bookings"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    test_id = Column(Integer, ForeignKey("lab_tests.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Booking reference
    booking_reference = Column(String(50), unique=True, nullable=False, index=True)
    
    # Patient information
    patient_name = Column(String(100), nullable=False)
    patient_age = Column(Integer, nullable=False)
    patient_gender = Column(String(20), nullable=False)
    
    # Appointment details
    appointment_date = Column(DateTime(timezone=True), nullable=False, index=True)
    home_collection = Column(Boolean, default=False, nullable=False)
    address = Column(Text, nullable=True)
    phone_number = Column(String(20), nullable=False)
    special_instructions = Column(Text, nullable=True)
    
    # Booking management
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING, nullable=False, index=True)
    
    # Notes and tracking
    admin_notes = Column(Text, nullable=True)  # Internal notes for admin/lab technician
    cancellation_reason = Column(Text, nullable=True)  # Reason for cancellation
    
    # Audit fields
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    test = relationship("LabTest", back_populates="bookings")
    user = relationship("User", back_populates="bookings")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_booking_user_status', 'user_id', 'status'),
        Index('idx_booking_test_date', 'test_id', 'appointment_date'),
        Index('idx_booking_date_status', 'appointment_date', 'status'),
        Index('idx_booking_created_at', 'created_at'),
        Index('idx_booking_reference', 'booking_reference'),
    )
    
    def __repr__(self):
        return f"<Booking(id={self.id}, reference='{self.booking_reference}', patient='{self.patient_name}', status='{self.status.value}')>"
    
    def __init__(self, **kwargs):
        """Initialize booking with auto-generated reference"""
        if 'booking_reference' not in kwargs:
            kwargs['booking_reference'] = self.generate_booking_reference()
        super().__init__(**kwargs)
    
    @staticmethod
    def generate_booking_reference():
        """Generate unique booking reference"""
        import secrets
        import string
        
        # Generate a 8-character alphanumeric reference
        chars = string.ascii_uppercase + string.digits
        reference = 'BK' + ''.join(secrets.choice(chars) for _ in range(6))
        return reference
    
    @property
    def is_upcoming(self):
        """Check if booking is upcoming"""
        from datetime import datetime, timezone
        return self.appointment_date > datetime.now(timezone.utc) and self.status in [BookingStatus.PENDING, BookingStatus.CONFIRMED]
    
    @property
    def is_cancellable(self):
        """Check if booking can be cancelled"""
        return self.status in [BookingStatus.PENDING, BookingStatus.CONFIRMED] and self.is_upcoming
    
    @property
    def is_modifiable(self):
        """Check if booking can be modified"""
        return self.status == BookingStatus.PENDING and self.is_upcoming
    
    def can_be_completed(self):
        """Check if booking can be marked as completed"""
        return self.status == BookingStatus.CONFIRMED
    
    def cancel(self, reason=None):
        """Cancel the booking"""
        if not self.is_cancellable:
            raise ValueError("Booking cannot be cancelled")
        
        from datetime import datetime, timezone
        self.status = BookingStatus.CANCELLED
        self.cancellation_reason = reason
        self.cancelled_at = datetime.now(timezone.utc)
    
    def complete(self):
        """Mark booking as completed"""
        if not self.can_be_completed():
            raise ValueError("Booking cannot be completed")
        
        from datetime import datetime, timezone
        self.status = BookingStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
    
    def confirm(self):
        """Confirm the booking"""
        if self.status != BookingStatus.PENDING:
            raise ValueError("Only pending bookings can be confirmed")
        
        self.status = BookingStatus.CONFIRMED
    
    def mark_no_show(self):
        """Mark booking as no show"""
        if self.status != BookingStatus.CONFIRMED:
            raise ValueError("Only confirmed bookings can be marked as no show")
        
        self.status = BookingStatus.NO_SHOW