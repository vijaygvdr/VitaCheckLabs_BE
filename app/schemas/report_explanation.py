from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ProcessingStatus(str, Enum):
    """Status of report explanation processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AbnormalityStatus(str, Enum):
    """Status of medical test values."""
    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"


class AbnormalitySeverity(str, Enum):
    """Severity level of abnormal values."""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"


class MedicalValue(BaseModel):
    """Schema for a parsed medical test value."""
    value: float = Field(..., description="Numeric test value")
    unit: str = Field("", description="Unit of measurement")
    reference_range: Optional[Dict[str, Any]] = Field(None, description="Reference range information")

    class Config:
        json_schema_extra = {
            "example": {
                "value": 95.0,
                "unit": "mg/dL",
                "reference_range": {
                    "min": 70,
                    "max": 100,
                    "unit": "mg/dL"
                }
            }
        }


class AbnormalFinding(BaseModel):
    """Schema for abnormal test finding."""
    value: float = Field(..., description="Test value")
    status: AbnormalityStatus = Field(..., description="Normal, low, or high")
    severity: AbnormalitySeverity = Field(..., description="Severity level")
    reference_min: float = Field(..., description="Reference range minimum")
    reference_max: float = Field(..., description="Reference range maximum")
    unit: str = Field("", description="Unit of measurement")

    class Config:
        json_schema_extra = {
            "example": {
                "value": 250.0,
                "status": "high",
                "severity": "moderate",
                "reference_min": 0,
                "reference_max": 200,
                "unit": "mg/dL"
            }
        }


class ReportSummaries(BaseModel):
    """Schema for dual AI-generated summaries."""
    patient_summary: Optional[str] = Field(None, description="Patient-friendly explanation")
    clinician_summary: Optional[str] = Field(None, description="Clinical professional summary")

    class Config:
        json_schema_extra = {
            "example": {
                "patient_summary": "Your cholesterol level is slightly higher than normal. This is common and can usually be improved with diet and exercise. Please discuss with your doctor about lifestyle changes.",
                "clinician_summary": "Total cholesterol elevated at 250 mg/dL (ref: <200). Recommend lipid panel follow-up in 3 months and lifestyle counseling."
            }
        }


class AnalysisMetadata(BaseModel):
    """Schema for analysis metadata."""
    total_tests: int = Field(0, description="Number of medical tests identified")
    abnormal_count: int = Field(0, description="Number of abnormal values")
    processed_at: Optional[datetime] = Field(None, description="When analysis completed")
    ai_enabled: bool = Field(False, description="Whether AI processing was used")

    class Config:
        json_schema_extra = {
            "example": {
                "total_tests": 8,
                "abnormal_count": 2,
                "processed_at": "2024-01-15T10:30:00Z",
                "ai_enabled": True
            }
        }


class ReportExplanationRequest(BaseModel):
    """Schema for requesting report explanation."""
    force_reprocess: bool = Field(False, description="Force reprocessing even if explanation exists")

    class Config:
        json_schema_extra = {
            "example": {
                "force_reprocess": False
            }
        }


class ReportExplanationResponse(BaseModel):
    """Schema for report explanation response."""
    id: str = Field(..., description="Explanation ID")
    report_id: str = Field(..., description="Associated report ID")

    # Content
    extracted_text: Optional[str] = Field(None, description="Text extracted from PDF")
    parsed_values: Optional[Dict[str, MedicalValue]] = Field(None, description="Parsed medical values")
    abnormal_findings: Optional[Dict[str, AbnormalFinding]] = Field(None, description="Abnormal findings")

    # Summaries
    patient_summary: Optional[str] = Field(None, description="Patient-friendly summary")
    clinician_summary: Optional[str] = Field(None, description="Clinical summary")

    # Metadata
    total_tests_parsed: int = Field(0, description="Number of tests parsed")
    abnormal_count: int = Field(0, description="Number of abnormal values")
    ai_confidence_score: Optional[float] = Field(None, description="AI confidence (0-1)")

    # Status
    processing_status: ProcessingStatus = Field(..., description="Processing status")
    error_message: Optional[str] = Field(None, description="Error message if failed")

    # AI info
    ai_model_used: Optional[str] = Field(None, description="AI model used")
    ai_enabled: bool = Field(False, description="Whether AI was used")

    # Timestamps
    created_at: datetime = Field(..., description="When explanation was created")
    updated_at: datetime = Field(..., description="When explanation was last updated")
    processed_at: Optional[datetime] = Field(None, description="When processing completed")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "exp_12345",
                "report_id": "rpt_67890",
                "extracted_text": "Blood glucose: 95 mg/dL...",
                "parsed_values": {
                    "glucose": {
                        "value": 95.0,
                        "unit": "mg/dL",
                        "reference_range": {"min": 70, "max": 100}
                    }
                },
                "abnormal_findings": {},
                "patient_summary": "Your blood glucose level is normal...",
                "clinician_summary": "All values within normal limits...",
                "total_tests_parsed": 5,
                "abnormal_count": 0,
                "ai_confidence_score": 0.95,
                "processing_status": "completed",
                "error_message": None,
                "ai_model_used": "gpt-4o-mini",
                "ai_enabled": True,
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T10:00:00Z",
                "processed_at": "2024-01-15T10:05:00Z"
            }
        }


class ReportExplanationSummary(BaseModel):
    """Simplified schema for listing explanations."""
    id: str = Field(..., description="Explanation ID")
    report_id: str = Field(..., description="Associated report ID")
    processing_status: ProcessingStatus = Field(..., description="Processing status")
    total_tests_parsed: int = Field(0, description="Number of tests parsed")
    abnormal_count: int = Field(0, description="Number of abnormal values")
    ai_enabled: bool = Field(False, description="Whether AI was used")
    created_at: datetime = Field(..., description="When explanation was created")
    processed_at: Optional[datetime] = Field(None, description="When processing completed")

    class Config:
        from_attributes = True


class ReportAnalysisResult(BaseModel):
    """Schema for complete analysis result."""
    extracted_text: str = Field(..., description="Full extracted text")
    parsed_values: Dict[str, MedicalValue] = Field(..., description="Parsed medical values")
    abnormal_findings: Dict[str, AbnormalFinding] = Field(..., description="Abnormal findings")
    summaries: ReportSummaries = Field(..., description="AI-generated summaries")
    analysis_metadata: AnalysisMetadata = Field(..., description="Analysis metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "extracted_text": "Complete blood count results...",
                "parsed_values": {
                    "glucose": {"value": 95.0, "unit": "mg/dL"},
                    "cholesterol": {"value": 180.0, "unit": "mg/dL"}
                },
                "abnormal_findings": {},
                "summaries": {
                    "patient_summary": "Your test results look good...",
                    "clinician_summary": "All parameters within normal limits..."
                },
                "analysis_metadata": {
                    "total_tests": 5,
                    "abnormal_count": 0,
                    "ai_enabled": True
                }
            }
        }


class AbnormalValuesFilter(BaseModel):
    """Filter for abnormal values analysis."""
    severity_levels: Optional[List[AbnormalitySeverity]] = Field(None, description="Filter by severity")
    test_names: Optional[List[str]] = Field(None, description="Filter by specific tests")

    class Config:
        json_schema_extra = {
            "example": {
                "severity_levels": ["moderate", "severe"],
                "test_names": ["glucose", "cholesterol"]
            }
        }


class BatchExplanationRequest(BaseModel):
    """Schema for batch processing multiple reports."""
    report_ids: List[str] = Field(..., description="List of report IDs to process")
    force_reprocess: bool = Field(False, description="Force reprocessing existing explanations")

    class Config:
        json_schema_extra = {
            "example": {
                "report_ids": ["rpt_123", "rpt_124", "rpt_125"],
                "force_reprocess": False
            }
        }


class BatchExplanationResponse(BaseModel):
    """Schema for batch processing response."""
    total_reports: int = Field(..., description="Total reports submitted")
    processing_started: int = Field(..., description="Number of reports that started processing")
    already_processed: int = Field(..., description="Number already processed")
    errors: List[str] = Field([], description="Any errors encountered")

    class Config:
        json_schema_extra = {
            "example": {
                "total_reports": 3,
                "processing_started": 2,
                "already_processed": 1,
                "errors": []
            }
        }