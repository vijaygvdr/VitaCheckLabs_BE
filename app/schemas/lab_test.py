from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum


class LabTestCategory(str, Enum):
    """Lab test categories"""
    BLOOD_TEST = "Blood Test"
    URINE_TEST = "Urine Test"
    IMAGING = "Imaging"
    PATHOLOGY = "Pathology"
    BIOCHEMISTRY = "Biochemistry"
    MICROBIOLOGY = "Microbiology"
    IMMUNOLOGY = "Immunology"
    HEMATOLOGY = "Hematology"
    ENDOCRINOLOGY = "Endocrinology"
    CARDIOLOGY = "Cardiology"
    OTHER = "Other"


class SampleType(str, Enum):
    """Sample types for lab tests"""
    BLOOD = "Blood"
    URINE = "Urine"
    SALIVA = "Saliva"
    STOOL = "Stool"
    TISSUE = "Tissue"
    SWAB = "Swab"
    OTHER = "Other"


class LabTestCreate(BaseModel):
    """Schema for creating a new lab test"""
    name: str = Field(..., min_length=1, max_length=200, description="Test name")
    code: str = Field(..., min_length=1, max_length=50, description="Unique test code")
    description: Optional[str] = Field(None, description="Test description")
    category: LabTestCategory = Field(..., description="Test category")
    sub_category: Optional[str] = Field(None, max_length=100, description="Test sub-category")
    sample_type: Optional[SampleType] = Field(None, description="Sample type required")
    requirements: Optional[str] = Field(None, description="Pre-test requirements")
    procedure: Optional[str] = Field(None, description="Test procedure")
    price: Decimal = Field(..., gt=0, description="Test price")
    duration_minutes: Optional[int] = Field(None, gt=0, description="Test duration in minutes")
    report_delivery_hours: Optional[int] = Field(None, gt=0, description="Report delivery time in hours")
    is_active: bool = Field(True, description="Whether test is active")
    is_home_collection_available: bool = Field(False, description="Home collection availability")
    minimum_age: Optional[int] = Field(None, ge=0, description="Minimum age for test")
    maximum_age: Optional[int] = Field(None, le=120, description="Maximum age for test")
    reference_ranges: Optional[str] = Field(None, description="Reference ranges as JSON")
    units: Optional[str] = Field(None, max_length=50, description="Measurement units")

    @validator('maximum_age')
    def validate_age_range(cls, v, values):
        if v is not None and 'minimum_age' in values and values['minimum_age'] is not None:
            if v <= values['minimum_age']:
                raise ValueError('Maximum age must be greater than minimum age')
        return v


class LabTestUpdate(BaseModel):
    """Schema for updating a lab test"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Test name")
    description: Optional[str] = Field(None, description="Test description")
    category: Optional[LabTestCategory] = Field(None, description="Test category")
    sub_category: Optional[str] = Field(None, max_length=100, description="Test sub-category")
    sample_type: Optional[SampleType] = Field(None, description="Sample type required")
    requirements: Optional[str] = Field(None, description="Pre-test requirements")
    procedure: Optional[str] = Field(None, description="Test procedure")
    price: Optional[Decimal] = Field(None, gt=0, description="Test price")
    duration_minutes: Optional[int] = Field(None, gt=0, description="Test duration in minutes")
    report_delivery_hours: Optional[int] = Field(None, gt=0, description="Report delivery time in hours")
    is_active: Optional[bool] = Field(None, description="Whether test is active")
    is_home_collection_available: Optional[bool] = Field(None, description="Home collection availability")
    minimum_age: Optional[int] = Field(None, ge=0, description="Minimum age for test")
    maximum_age: Optional[int] = Field(None, le=120, description="Maximum age for test")
    reference_ranges: Optional[str] = Field(None, description="Reference ranges as JSON")
    units: Optional[str] = Field(None, max_length=50, description="Measurement units")


class LabTestResponse(BaseModel):
    """Schema for lab test response"""
    id: int
    name: str
    code: str
    description: Optional[str] = None
    category: str
    sub_category: Optional[str] = None
    sample_type: Optional[str] = None
    requirements: Optional[str] = None
    procedure: Optional[str] = None
    price: Decimal
    duration_minutes: Optional[int] = None
    report_delivery_hours: Optional[int] = None
    is_active: bool
    is_home_collection_available: bool
    minimum_age: Optional[int] = None
    maximum_age: Optional[int] = None
    reference_ranges: Optional[str] = None
    units: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Computed fields
    display_name: str
    price_formatted: str

    model_config = {"from_attributes": True}


class LabTestListResponse(BaseModel):
    """Schema for paginated lab test list response"""
    tests: List[LabTestResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class LabTestFilter(BaseModel):
    """Schema for lab test filtering"""
    category: Optional[LabTestCategory] = Field(None, description="Filter by category")
    sample_type: Optional[SampleType] = Field(None, description="Filter by sample type")
    min_price: Optional[Decimal] = Field(None, ge=0, description="Minimum price filter")
    max_price: Optional[Decimal] = Field(None, ge=0, description="Maximum price filter")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_home_collection_available: Optional[bool] = Field(None, description="Filter by home collection")
    search: Optional[str] = Field(None, min_length=1, description="Search in name and description")


class LabTestCategoryResponse(BaseModel):
    """Schema for lab test category response"""
    category: str
    count: int
    sub_categories: List[str]


class LabTestBooking(BaseModel):
    """Schema for booking a lab test"""
    test_id: int = Field(..., description="Lab test ID")
    patient_name: str = Field(..., min_length=1, max_length=100, description="Patient name")
    patient_age: int = Field(..., ge=0, le=120, description="Patient age")
    patient_gender: str = Field(..., description="Patient gender")
    appointment_date: datetime = Field(..., description="Preferred appointment date")
    home_collection: bool = Field(False, description="Request home collection")
    address: Optional[str] = Field(None, description="Address for home collection")
    phone_number: str = Field(..., min_length=10, max_length=20, description="Contact phone number")
    special_instructions: Optional[str] = Field(None, description="Special instructions")

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


class LabTestBookingResponse(BaseModel):
    """Schema for lab test booking response"""
    id: int
    test: LabTestResponse
    patient_name: str
    patient_age: int
    patient_gender: str
    appointment_date: datetime
    home_collection: bool
    address: Optional[str] = None
    phone_number: str
    special_instructions: Optional[str] = None
    booking_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LabTestStats(BaseModel):
    """Schema for lab test statistics"""
    total_tests: int
    active_tests: int
    categories_count: int
    average_price: Decimal
    most_popular_category: str
    home_collection_available: int