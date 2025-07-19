from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.models.booking import BookingStatus
from app.schemas.lab_test import LabTestResponse
from app.schemas.auth import UserResponse


class BookingStatusUpdate(BaseModel):
    """Schema for updating booking status"""
    status: BookingStatus
    admin_notes: Optional[str] = Field(None, max_length=500, description="Admin notes for status change")


class BookingCancellation(BaseModel):
    """Schema for cancelling a booking"""
    cancellation_reason: Optional[str] = Field(None, max_length=500, description="Reason for cancellation")


class BookingAdminUpdate(BaseModel):
    """Schema for admin booking updates"""
    status: Optional[BookingStatus] = None
    admin_notes: Optional[str] = Field(None, max_length=500)
    appointment_date: Optional[datetime] = None
    
    @validator('appointment_date')
    def validate_appointment_date(cls, v):
        if v:
            from datetime import timezone
            # Handle both timezone-aware and timezone-naive datetimes
            now = datetime.now(timezone.utc)
            if v.tzinfo is None:
                # If input is timezone-naive, assume UTC
                v = v.replace(tzinfo=timezone.utc)
            if v <= now:
                raise ValueError('Appointment date must be in the future')
        return v


class BookingResponse(BaseModel):
    """Complete booking response schema"""
    id: int
    booking_reference: str
    
    # Patient information
    patient_name: str
    patient_age: int
    patient_gender: str
    
    # Appointment details
    appointment_date: datetime
    home_collection: bool
    address: Optional[str]
    phone_number: str
    special_instructions: Optional[str]
    
    # Booking management
    status: BookingStatus
    admin_notes: Optional[str]
    cancellation_reason: Optional[str]
    
    # Audit fields
    created_at: datetime
    updated_at: datetime
    cancelled_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    # Related objects
    test: LabTestResponse
    user: UserResponse
    
    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    """Simplified booking response for list views"""
    id: int
    booking_reference: str
    patient_name: str
    patient_age: int
    appointment_date: datetime
    status: BookingStatus
    home_collection: bool
    created_at: datetime
    
    # Test information
    test_name: str
    test_code: str
    test_price: float
    
    # User information
    user_email: str
    user_name: str
    
    class Config:
        from_attributes = True


class BookingFilterParams(BaseModel):
    """Query parameters for filtering bookings"""
    status: Optional[BookingStatus] = None
    user_id: Optional[int] = None
    test_id: Optional[int] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    home_collection: Optional[bool] = None
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(50, ge=1, le=100, description="Page size")
    
    @validator('date_to')
    def validate_date_range(cls, v, values):
        if v and 'date_from' in values and values['date_from'] and v <= values['date_from']:
            raise ValueError('date_to must be after date_from')
        return v


class BookingStatsResponse(BaseModel):
    """Booking statistics response"""
    total_bookings: int
    pending_bookings: int
    confirmed_bookings: int
    completed_bookings: int
    cancelled_bookings: int
    no_show_bookings: int
    today_bookings: int
    upcoming_bookings: int
    home_collection_bookings: int
    
    class Config:
        from_attributes = True


class BookingCalendarEvent(BaseModel):
    """Booking calendar event for calendar views"""
    id: int
    title: str  # Patient name + test name
    start: datetime  # appointment_date
    end: datetime  # appointment_date + estimated duration
    status: BookingStatus
    color: str  # Color based on status
    patient_name: str
    test_name: str
    phone_number: str
    home_collection: bool
    
    class Config:
        from_attributes = True


# Reuse existing booking schemas from lab_test.py for compatibility
class BookingCreate(BaseModel):
    """Schema for creating a new booking (reused from lab_test.py)"""
    patient_name: str = Field(..., min_length=1, max_length=100, description="Patient full name")
    patient_age: int = Field(..., ge=0, le=120, description="Patient age in years")
    patient_gender: str = Field(..., min_length=1, max_length=20, description="Patient gender")
    appointment_date: datetime = Field(..., description="Preferred appointment date and time")
    home_collection: bool = Field(False, description="Whether home collection is required")
    address: Optional[str] = Field(None, max_length=500, description="Address for home collection")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Contact phone number")
    special_instructions: Optional[str] = Field(None, max_length=500, description="Special instructions or notes")

    @validator('appointment_date')
    def validate_appointment_date(cls, v):
        from datetime import timezone
        # Handle both timezone-aware and timezone-naive datetimes
        now = datetime.now(timezone.utc)
        if v.tzinfo is None:
            # If input is timezone-naive, assume UTC
            v = v.replace(tzinfo=timezone.utc)
        if v <= now:
            raise ValueError('Appointment date must be in the future')
        return v

    @validator('address')
    def validate_address_for_home_collection(cls, v, values):
        if values.get('home_collection') and not v:
            raise ValueError('Address is required for home collection')
        return v


class BookingCreateResponse(BaseModel):
    """Response schema for booking creation"""
    id: int
    booking_reference: str
    patient_name: str
    patient_age: int
    patient_gender: str
    appointment_date: datetime
    home_collection: bool
    address: Optional[str]
    phone_number: str
    special_instructions: Optional[str]
    status: BookingStatus
    created_at: datetime
    test: LabTestResponse
    
    class Config:
        from_attributes = True