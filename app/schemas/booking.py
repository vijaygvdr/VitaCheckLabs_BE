from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime, date, time
from enum import Enum
from decimal import Decimal

class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

class CollectionType(str, Enum):
    LAB_VISIT = "lab_visit"
    HOME_COLLECTION = "home_collection"

class TimeSlot(BaseModel):
    start_time: time
    end_time: time
    is_available: bool = True

class BookingBase(BaseModel):
    patient_name: str
    patient_email: Optional[EmailStr] = None
    patient_phone: Optional[str] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    test_ids: Optional[List[str]] = []
    panel_ids: Optional[List[str]] = []
    appointment_date: Optional[datetime] = None
    appointment_time: Optional[time] = None
    collection_type: Optional[CollectionType] = None
    address: Optional[str] = None  # Required for home collection
    special_instructions: Optional[str] = None

class BookingCreate(BookingBase):
    """Create booking schema"""
    pass

class BookingUpdate(BaseModel):
    patient_name: Optional[str] = None
    patient_email: Optional[EmailStr] = None
    patient_phone: Optional[str] = None
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    collection_type: Optional[CollectionType] = None
    address: Optional[str] = None
    special_instructions: Optional[str] = None
    status: Optional[BookingStatus] = None
    payment_status: Optional[PaymentStatus] = None

class BookingResponse(BookingBase):
    id: str
    booking_reference: Optional[str] = None
    status: Optional[BookingStatus] = None
    payment_status: Optional[PaymentStatus] = None
    total_amount: Optional[Decimal] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class BookingListResponse(BaseModel):
    bookings: List[BookingResponse]
    total: int
    page: int
    size: int

class BookingFilter(BaseModel):
    status: Optional[BookingStatus] = None
    payment_status: Optional[PaymentStatus] = None
    collection_type: Optional[CollectionType] = None
    appointment_date: Optional[date] = None
    patient_email: Optional[EmailStr] = None

class AvailableSlot(BaseModel):
    date: date
    time_slots: List[TimeSlot]
    available_count: int

class SlotAvailability(BaseModel):
    date: date
    available_slots: List[TimeSlot]
    booked_slots: List[TimeSlot]
    total_capacity: int

class BookingStats(BaseModel):
    total_bookings: int
    pending_bookings: int
    confirmed_bookings: int
    completed_bookings: int
    cancelled_bookings: int
    revenue_total: Decimal
    revenue_pending: Decimal

class PaymentDetails(BaseModel):
    amount: Decimal
    payment_method: str
    transaction_id: Optional[str] = None
    payment_date: Optional[datetime] = None

class BookingConfirmation(BaseModel):
    booking_id: int
    confirmation_number: str
    patient_name: str
    appointment_details: str
    preparation_instructions: List[str]
    contact_info: Dict[str, str]

class BookingStatusUpdate(BaseModel):
    status: BookingStatus

class BookingAdminUpdate(BaseModel):
    patient_name: Optional[str] = None
    patient_email: Optional[EmailStr] = None
    patient_phone: Optional[str] = None
    appointment_date: Optional[date] = None
    appointment_time: Optional[time] = None
    collection_type: Optional[CollectionType] = None
    address: Optional[str] = None
    special_instructions: Optional[str] = None
    status: Optional[BookingStatus] = None
    payment_status: Optional[PaymentStatus] = None
    admin_notes: Optional[str] = None