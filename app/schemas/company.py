from typing import Optional, List
from pydantic import BaseModel, EmailStr
from datetime import datetime, time
from enum import Enum

class InquiryType(str, Enum):
    GENERAL = "general"
    SUPPORT = "support"
    BILLING = "billing"
    TECHNICAL = "technical"

class MessageStatus(str, Enum):
    NEW = "new"
    READ = "read"
    REPLIED = "replied"
    CLOSED = "closed"

class BusinessHours(BaseModel):
    day: str
    open_time: time
    close_time: time
    is_open: bool = True

class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class CompanySettings(BaseModel):
    allow_weekend_bookings: bool = False
    max_bookings_per_day: int = 50
    notification_email: EmailStr

class CompanyInfoBase(BaseModel):
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None

class CompanyInfoResponse(CompanyInfoBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class CompanyInfoUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None

class ContactInfoResponse(BaseModel):
    phone: str
    email: EmailStr
    address: str
    business_hours: List[BusinessHours]

class ServicesListResponse(BaseModel):
    services: List[str]
    total: int

class ContactFormSubmission(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    inquiry_type: InquiryType
    message: str

class ContactFormResponse(BaseModel):
    id: int
    submission_id: str
    message: str
    estimated_response_time: str

class ContactMessageBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    inquiry_type: InquiryType
    message: str
    status: MessageStatus = MessageStatus.NEW

class ContactMessageResponse(ContactMessageBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ContactMessageUpdate(BaseModel):
    status: Optional[MessageStatus] = None
    response: Optional[str] = None

class ContactMessageListResponse(BaseModel):
    messages: List[ContactMessageResponse]
    total: int
    page: int
    size: int

class ContactMessageFilter(BaseModel):
    status: Optional[MessageStatus] = None
    inquiry_type: Optional[InquiryType] = None
    email: Optional[EmailStr] = None

class ContactStats(BaseModel):
    total_messages: int
    new_messages: int
    pending_messages: int
    closed_messages: int

class CompanyProfileResponse(BaseModel):
    company_info: CompanyInfoResponse
    contact_info: ContactInfoResponse
    services: ServicesListResponse
    settings: CompanySettings