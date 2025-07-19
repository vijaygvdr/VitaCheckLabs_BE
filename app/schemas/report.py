from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class ReportStatus(str, Enum):
    """Report status options"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REVIEWED = "reviewed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    """Payment status options"""
    PENDING = "pending"
    PAID = "paid"
    REFUNDED = "refunded"


class Priority(str, Enum):
    """Priority levels"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class ReportCreate(BaseModel):
    """Schema for creating a new report"""
    user_id: int = Field(..., description="User ID for whom the report is created")
    lab_test_id: int = Field(..., description="Lab test ID")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled test date")
    collection_location: Optional[str] = Field(None, max_length=200, description="Collection location")
    collection_notes: Optional[str] = Field(None, description="Collection notes")
    priority: Priority = Field(Priority.NORMAL, description="Report priority")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('scheduled_at')
    def validate_scheduled_at(cls, v):
        if v:
            from datetime import timezone
            now = datetime.now(timezone.utc) if v.tzinfo else datetime.now()
            if v <= now:
                raise ValueError('Scheduled date must be in the future')
        return v


class ReportUpdate(BaseModel):
    """Schema for updating a report"""
    status: Optional[ReportStatus] = Field(None, description="Report status")
    scheduled_at: Optional[datetime] = Field(None, description="Scheduled test date")
    collected_at: Optional[datetime] = Field(None, description="Sample collection time")
    tested_at: Optional[datetime] = Field(None, description="Test performed time")
    reviewed_at: Optional[datetime] = Field(None, description="Results reviewed time")
    delivered_at: Optional[datetime] = Field(None, description="Report delivered time")
    sample_collected_by: Optional[str] = Field(None, max_length=100, description="Collector name")
    collection_location: Optional[str] = Field(None, max_length=200, description="Collection location")
    collection_notes: Optional[str] = Field(None, description="Collection notes")
    results: Optional[str] = Field(None, description="Test results JSON")
    observations: Optional[str] = Field(None, description="Doctor's observations")
    recommendations: Optional[str] = Field(None, description="Medical recommendations")
    is_verified: Optional[bool] = Field(None, description="Verification status")
    verified_by: Optional[str] = Field(None, max_length=100, description="Verifying doctor")
    verified_at: Optional[datetime] = Field(None, description="Verification time")
    amount_charged: Optional[int] = Field(None, ge=0, description="Amount in paisa")
    payment_status: Optional[PaymentStatus] = Field(None, description="Payment status")
    payment_reference: Optional[str] = Field(None, max_length=100, description="Payment reference")
    notes: Optional[str] = Field(None, description="Internal notes")
    priority: Optional[Priority] = Field(None, description="Report priority")


class ReportFileUpload(BaseModel):
    """Schema for report file upload"""
    file_original_name: str = Field(..., max_length=255, description="Original filename")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    file_type: str = Field(..., max_length=50, description="MIME type")


class ReportShare(BaseModel):
    """Schema for sharing a report"""
    shared_with: List[str] = Field(..., description="List of email addresses to share with")
    message: Optional[str] = Field(None, description="Optional message to include")

    @validator('shared_with')
    def validate_shared_with(cls, v):
        if not v:
            raise ValueError('At least one email address is required')
        # Basic email validation
        for email in v:
            if '@' not in email or '.' not in email:
                raise ValueError(f'Invalid email address: {email}')
        return v


class LabTestBasic(BaseModel):
    """Basic lab test info for report responses"""
    id: int
    name: str
    code: str
    category: str
    sub_category: Optional[str] = None

    model_config = {"from_attributes": True}


class UserBasic(BaseModel):
    """Basic user info for report responses"""
    id: int
    email: str
    full_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    """Schema for report response"""
    id: int
    report_number: str
    user_id: int
    lab_test_id: int
    status: str
    scheduled_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    tested_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    sample_collected_by: Optional[str] = None
    collection_location: Optional[str] = None
    collection_notes: Optional[str] = None
    results: Optional[str] = None
    observations: Optional[str] = None
    recommendations: Optional[str] = None
    file_path: Optional[str] = None
    file_original_name: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    is_shared: bool
    shared_at: Optional[datetime] = None
    shared_with: Optional[str] = None
    is_verified: bool
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    amount_charged: Optional[int] = None
    payment_status: str
    payment_reference: Optional[str] = None
    notes: Optional[str] = None
    priority: str
    created_at: datetime
    updated_at: datetime
    
    # Relationships
    lab_test: Optional[LabTestBasic] = None
    user: Optional[UserBasic] = None
    
    # Computed properties
    amount_in_rupees: Optional[float] = None
    can_be_downloaded: bool = False
    turnaround_time_hours: Optional[float] = None

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    """Schema for paginated report list response"""
    reports: List[ReportResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ReportFilter(BaseModel):
    """Schema for report filtering"""
    status: Optional[ReportStatus] = Field(None, description="Filter by status")
    lab_test_id: Optional[int] = Field(None, description="Filter by lab test")
    payment_status: Optional[PaymentStatus] = Field(None, description="Filter by payment status")
    priority: Optional[Priority] = Field(None, description="Filter by priority")
    is_verified: Optional[bool] = Field(None, description="Filter by verification status")
    date_from: Optional[datetime] = Field(None, description="Filter reports from date")
    date_to: Optional[datetime] = Field(None, description="Filter reports to date")
    search: Optional[str] = Field(None, min_length=1, description="Search in report number, notes")

    @validator('date_to')
    def validate_date_range(cls, v, values):
        if v and 'date_from' in values and values['date_from']:
            if v <= values['date_from']:
                raise ValueError('date_to must be after date_from')
        return v


class ReportStats(BaseModel):
    """Schema for report statistics"""
    total_reports: int
    pending_reports: int
    completed_reports: int
    average_turnaround_hours: float
    total_revenue: float
    paid_reports: int
    unpaid_reports: int
    verified_reports: int


class ReportDownload(BaseModel):
    """Schema for report download response"""
    download_url: str
    expires_at: datetime
    file_name: str
    file_size: int