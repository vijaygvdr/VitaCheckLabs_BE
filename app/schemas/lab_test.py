from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from enum import Enum
from decimal import Decimal

class TestCategory(str, Enum):
    BLOOD = "Blood Test"
    URINE = "Urine Test"
    RADIOLOGY = "Radiology"
    PATHOLOGY = "Pathology"
    CARDIOLOGY = "Cardiology"

class TestStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"

class LabTestBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    category: TestCategory
    price: Decimal
    units: Optional[str] = None
    normal_range: Optional[str] = None
    sample_type: Optional[str] = None
    preparation_instructions: Optional[str] = None
    turnaround_time: Optional[str] = None
    status: TestStatus = TestStatus.ACTIVE

class LabTestCreate(LabTestBase):
    """Create lab test schema"""
    pass

class LabTestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[TestCategory] = None
    price: Optional[Decimal] = None
    units: Optional[str] = None
    normal_range: Optional[str] = None
    sample_type: Optional[str] = None
    preparation_instructions: Optional[str] = None
    turnaround_time: Optional[str] = None
    status: Optional[TestStatus] = None

class LabTestResponse(LabTestBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TestPanelBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    category: TestCategory
    price: Decimal
    included_tests: List[int]  # List of test IDs
    preparation_instructions: Optional[str] = None
    turnaround_time: Optional[str] = None
    status: TestStatus = TestStatus.ACTIVE

class TestPanelCreate(TestPanelBase):
    """Create test panel schema"""
    pass

class TestPanelResponse(TestPanelBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    included_test_details: List[LabTestResponse]

    class Config:
        from_attributes = True

class LabTestListResponse(BaseModel):
    tests: List[LabTestResponse]
    total: int
    page: int
    size: int

class TestPanelListResponse(BaseModel):
    panels: List[TestPanelResponse]
    total: int
    page: int
    size: int

class LabTestFilter(BaseModel):
    category: Optional[TestCategory] = None
    status: Optional[TestStatus] = None
    search: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None

class TestStats(BaseModel):
    total_tests: int
    active_tests: int
    total_panels: int
    active_panels: int
    categories: Dict[str, int]

class PriceRange(BaseModel):
    min_price: Decimal
    max_price: Decimal
    average_price: Decimal