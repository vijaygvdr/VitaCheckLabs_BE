from typing import Optional, List, Any, Dict
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class ReportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"

class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class ReportBase(BaseModel):
    patient_name: str
    patient_age: Optional[int] = None
    test_type: str
    status: ReportStatus = ReportStatus.PENDING

class ReportCreate(ReportBase):
    """Create report schema"""
    pass

class ReportUpdate(BaseModel):
    patient_name: Optional[str] = None
    patient_age: Optional[int] = None
    test_type: Optional[str] = None
    status: Optional[ReportStatus] = None

class ReportResponse(ReportBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ReportListResponse(BaseModel):
    reports: List[ReportResponse]
    total: int
    page: int
    size: int

class ReportFilter(BaseModel):
    status: Optional[ReportStatus] = None
    test_type: Optional[str] = None
    patient_name: Optional[str] = None

class ReportStats(BaseModel):
    total_reports: int
    pending_reports: int
    completed_reports: int
    failed_reports: int

class ReportShare(BaseModel):
    recipient_email: str
    message: Optional[str] = None

class ReportFileUpload(BaseModel):
    filename: str
    content_type: str
    file_size: int

class ReportDownload(BaseModel):
    report_id: int
    download_url: str
    expires_at: datetime