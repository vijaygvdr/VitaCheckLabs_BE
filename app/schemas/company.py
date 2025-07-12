from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator, EmailStr
from enum import Enum


class InquiryType(str, Enum):
    """Contact inquiry types"""
    GENERAL = "general"
    SUPPORT = "support"
    COMPLAINT = "complaint"
    FEEDBACK = "feedback"
    APPOINTMENT = "appointment"
    BILLING = "billing"


class MessageStatus(str, Enum):
    """Contact message status"""
    NEW = "new"
    READ = "read"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Priority(str, Enum):
    """Message priority levels"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# Company Information Schemas
class CompanyInfoResponse(BaseModel):
    """Schema for company information response"""
    id: int
    name: str
    legal_name: Optional[str] = None
    description: Optional[str] = None
    mission_statement: Optional[str] = None
    vision_statement: Optional[str] = None
    tagline: Optional[str] = None
    established_year: Optional[int] = None
    license_number: Optional[str] = None
    accreditation: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyInfoUpdate(BaseModel):
    """Schema for updating company information (admin only)"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    legal_name: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None)
    mission_statement: Optional[str] = Field(None)
    vision_statement: Optional[str] = Field(None)
    tagline: Optional[str] = Field(None, max_length=200)
    established_year: Optional[int] = Field(None, ge=1900, le=2030)
    license_number: Optional[str] = Field(None, max_length=100)
    accreditation: Optional[str] = Field(None, max_length=200)
    logo_url: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


# Contact Information Schemas
class ContactInfoResponse(BaseModel):
    """Schema for company contact information response"""
    email: Optional[str] = None
    phone_primary: Optional[str] = None
    phone_secondary: Optional[str] = None
    emergency_contact: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "India"
    full_address: str
    google_maps_link: Optional[str] = None
    operating_hours: Optional[Dict[str, Any]] = None
    is_24x7: bool = False
    accepts_home_collection: bool = True
    home_collection_radius_km: Optional[int] = None
    social_media_links: Optional[Dict[str, str]] = None

    model_config = {"from_attributes": True}


# Services Schemas
class ServiceResponse(BaseModel):
    """Schema for individual service response"""
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True


class ServicesListResponse(BaseModel):
    """Schema for services list response"""
    services: List[str]
    specializations: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    total_services: int


# Contact Form Schemas
class ContactFormSubmission(BaseModel):
    """Schema for contact form submission"""
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    subject: str = Field(..., min_length=5, max_length=200, description="Message subject")
    message: str = Field(..., min_length=10, description="Message content")
    inquiry_type: InquiryType = Field(InquiryType.GENERAL, description="Type of inquiry")
    source: str = Field("website", description="Message source")

    @validator('phone')
    def validate_phone(cls, v):
        if v and len(v.replace(' ', '').replace('+', '').replace('-', '')) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        return v


class ContactMessageResponse(BaseModel):
    """Schema for contact message response"""
    id: int
    full_name: str
    email: str
    phone: Optional[str] = None
    subject: str
    message: str
    inquiry_type: Optional[str] = None
    status: str
    priority: str
    responded_at: Optional[datetime] = None
    response_message: Optional[str] = None
    responded_by: Optional[str] = None
    source: str
    follow_up_required: bool
    follow_up_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed properties
    is_urgent: bool = False
    response_time_hours: Optional[float] = None

    model_config = {"from_attributes": True}


class ContactFormResponse(BaseModel):
    """Schema for contact form submission response"""
    message: str
    contact_id: int
    estimated_response_time: str
    support_email: str
    support_phone: Optional[str] = None


# Admin Schemas for Contact Management
class ContactMessageUpdate(BaseModel):
    """Schema for updating contact message (admin only)"""
    status: Optional[MessageStatus] = None
    priority: Optional[Priority] = None
    response_message: Optional[str] = None
    responded_by: Optional[str] = Field(None, max_length=100)
    follow_up_required: Optional[bool] = None
    follow_up_date: Optional[datetime] = None
    internal_notes: Optional[str] = None


class ContactMessageListResponse(BaseModel):
    """Schema for paginated contact messages list"""
    messages: List[ContactMessageResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ContactMessageFilter(BaseModel):
    """Schema for filtering contact messages"""
    status: Optional[MessageStatus] = None
    inquiry_type: Optional[InquiryType] = None
    priority: Optional[Priority] = None
    responded: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = Field(None, min_length=1, description="Search in name, email, subject, message")

    @validator('date_to')
    def validate_date_range(cls, v, values):
        if v and 'date_from' in values and values['date_from']:
            if v <= values['date_from']:
                raise ValueError('date_to must be after date_from')
        return v


# Statistics Schemas
class ContactStats(BaseModel):
    """Schema for contact messages statistics"""
    total_messages: int
    new_messages: int
    pending_response: int
    resolved_messages: int
    average_response_time_hours: float
    urgent_messages: int
    messages_this_week: int
    messages_this_month: int


# Business Hours Schema
class BusinessHours(BaseModel):
    """Schema for business operating hours"""
    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None

    @validator('*', pre=True)
    def validate_time_format(cls, v):
        """Validate time format (e.g., '09:00-17:00' or 'Closed')"""
        if v and v.lower() != 'closed':
            # Basic validation for time range format
            if '-' not in v or len(v.split('-')) != 2:
                raise ValueError('Time format should be HH:MM-HH:MM or "Closed"')
        return v


# Company Settings Schema
class CompanySettings(BaseModel):
    """Schema for company business settings"""
    accepts_home_collection: bool = True
    home_collection_radius_km: int = Field(25, ge=1, le=100)
    minimum_order_amount: int = Field(0, ge=0, description="Minimum order amount in paisa")
    is_24x7: bool = False
    emergency_contact: Optional[str] = None
    operating_hours: Optional[BusinessHours] = None


# Complete Company Profile Schema
class CompanyProfileResponse(BaseModel):
    """Schema for complete company profile"""
    info: CompanyInfoResponse
    contact: ContactInfoResponse
    services: ServicesListResponse
    settings: CompanySettings

    model_config = {"from_attributes": True}