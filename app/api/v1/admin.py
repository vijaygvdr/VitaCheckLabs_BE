"""
Admin API endpoints for data management and seeding
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from pydantic import BaseModel

from app.services.dynamodb_service import (
    lab_test_service,
    ai_rules_service,
    agent_audit_service,
    reminders_service
)


router = APIRouter()


# Pydantic models for request bodies
class LabTestData(BaseModel):
    name: str
    code: str
    description: str = ""
    type: str = "test"  # "test" or "panel"
    tests_included: List[str] = []  # For panels
    category: str
    sub_category: str = ""
    sample_type: str = ""
    requirements: str = ""
    procedure: str = ""
    price: float
    duration_minutes: int = 30
    report_delivery_hours: int = 24
    is_active: bool = True
    is_home_collection_available: bool = False
    minimum_age: int = None
    maximum_age: int = None
    reference_ranges: str = ""
    units: str = ""


class AIRuleData(BaseModel):
    name: str
    description: str = ""
    symptoms: List[str]
    synonyms: List[str] = []
    panel_code: str
    weight: float = 0.5
    rationale: str = ""
    disclaimers: List[str] = []
    age_min: int = None
    age_max: int = None
    gender_specific: str = None
    requires_confirmation: bool = True
    is_active: bool = True


class BulkLabTestsRequest(BaseModel):
    individual_tests: List[LabTestData] = []
    test_panels: List[LabTestData] = []


class BulkAIRulesRequest(BaseModel):
    rules: List[AIRuleData]


# Lab Tests Seeding Endpoints
@router.post("/seed/lab-tests")
async def seed_lab_tests(data: BulkLabTestsRequest):
    """
    Seed lab tests and panels via API

    Request body example:
    {
      "individual_tests": [
        {
          "name": "TSH",
          "code": "TSH",
          "description": "Thyroid Stimulating Hormone",
          "type": "test",
          "category": "Blood Test",
          "price": 250.0,
          "is_active": true
        }
      ],
      "test_panels": [
        {
          "name": "TFT Basic",
          "code": "TFT-BASIC",
          "type": "panel",
          "tests_included": ["tsh-001", "ft4-001"],
          "category": "Blood Test",
          "price": 500.0
        }
      ]
    }
    """
    try:
        created_tests = []
        created_panels = []

        # Create individual tests first
        for test_data in data.individual_tests:
            try:
                # Check if test already exists
                existing = lab_test_service.get_test_by_code(test_data.code)
                if existing:
                    print(f"Test {test_data.code} already exists, skipping...")
                    continue

                created_test = lab_test_service.create_test(test_data.dict())
                created_tests.append({
                    "test_id": created_test["test_id"],
                    "name": created_test["name"],
                    "code": created_test["code"]
                })
            except Exception as e:
                print(f"Error creating test {test_data.code}: {str(e)}")

        # Create panels
        for panel_data in data.test_panels:
            try:
                # Check if panel already exists
                existing = lab_test_service.get_test_by_code(panel_data.code)
                if existing:
                    print(f"Panel {panel_data.code} already exists, skipping...")
                    continue

                created_panel = lab_test_service.create_test(panel_data.dict())
                created_panels.append({
                    "test_id": created_panel["test_id"],
                    "name": created_panel["name"],
                    "code": created_panel["code"]
                })
            except Exception as e:
                print(f"Error creating panel {panel_data.code}: {str(e)}")

        return {
            "success": True,
            "message": f"Seeded {len(created_tests)} tests and {len(created_panels)} panels",
            "created_tests": created_tests,
            "created_panels": created_panels
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Seeding failed: {str(e)}")


@router.post("/seed/ai-rules")
async def seed_ai_rules(data: BulkAIRulesRequest):
    """
    Seed AI rules via API

    Request body example:
    {
      "rules": [
        {
          "name": "Fatigue → TFT Basic",
          "symptoms": ["fatigue", "tired", "exhaustion"],
          "synonyms": ["worn out", "drained"],
          "panel_code": "TFT-BASIC",
          "weight": 0.85,
          "rationale": "Fatigue is commonly associated with thyroid dysfunction...",
          "disclaimers": ["Multiple causes possible", "Consult healthcare provider"]
        }
      ]
    }
    """
    try:
        created_rules = []

        for rule_data in data.rules:
            try:
                created_rule = ai_rules_service.create_rule(rule_data.dict())
                created_rules.append({
                    "rule_id": created_rule["rule_id"],
                    "name": created_rule["name"],
                    "panel_code": created_rule["panel_code"],
                    "weight": created_rule["weight"]
                })
            except Exception as e:
                print(f"Error creating rule {rule_data.name}: {str(e)}")

        return {
            "success": True,
            "message": f"Seeded {len(created_rules)} AI rules",
            "created_rules": created_rules
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI rules seeding failed: {str(e)}")


# Individual CRUD endpoints for real-time management
@router.post("/lab-tests")
async def create_lab_test(test_data: LabTestData):
    """Create a single lab test or panel"""
    try:
        # Check if already exists
        existing = lab_test_service.get_test_by_code(test_data.code)
        if existing:
            raise HTTPException(status_code=400, detail=f"Test with code {test_data.code} already exists")

        created_test = lab_test_service.create_test(test_data.dict())
        return {
            "success": True,
            "test": {
                "test_id": created_test["test_id"],
                "name": created_test["name"],
                "code": created_test["code"],
                "type": created_test["type"],
                "price": created_test["price"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create test: {str(e)}")


@router.post("/ai-rules")
async def create_ai_rule(rule_data: AIRuleData):
    """Create a single AI rule"""
    try:
        created_rule = ai_rules_service.create_rule(rule_data.dict())
        return {
            "success": True,
            "rule": {
                "rule_id": created_rule["rule_id"],
                "name": created_rule["name"],
                "panel_code": created_rule["panel_code"],
                "weight": created_rule["weight"],
                "is_active": created_rule["is_active"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create AI rule: {str(e)}")


@router.put("/ai-rules/{rule_id}")
async def update_ai_rule(rule_id: str, updates: Dict[str, Any]):
    """Update an AI rule"""
    try:
        success = ai_rules_service.update_rule(rule_id, updates)
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found or update failed")

        updated_rule = ai_rules_service.get_rule_by_id(rule_id)
        return {
            "success": True,
            "rule": updated_rule
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update rule: {str(e)}")


@router.get("/ai-rules")
async def get_ai_rules(active_only: bool = True):
    """Get all AI rules"""
    try:
        if active_only:
            rules = ai_rules_service.get_active_rules()
        else:
            # For admin view, you might want all rules - implement get_all_rules if needed
            rules = ai_rules_service.get_active_rules()

        return {
            "success": True,
            "rules": rules,
            "count": len(rules)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rules: {str(e)}")


@router.get("/lab-tests")
async def get_lab_tests(test_type: str = None, active_only: bool = True):
    """Get lab tests and panels"""
    try:
        if test_type == "panel":
            tests = lab_test_service.get_panels(is_active=active_only)
        elif test_type == "test":
            tests = lab_test_service.get_individual_tests(is_active=active_only)
        else:
            tests = lab_test_service.get_all_tests(is_active=active_only)

        return {
            "success": True,
            "tests": tests,
            "count": len(tests)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tests: {str(e)}")


@router.get("/lab-tests/{test_id}/panel-details")
async def get_panel_details(test_id: str):
    """Get panel with included test details"""
    try:
        panel = lab_test_service.get_panel_with_included_tests(test_id)
        if not panel:
            raise HTTPException(status_code=404, detail="Panel not found")

        return {
            "success": True,
            "panel": panel
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get panel details: {str(e)}")


# Quick seed endpoints with predefined data
@router.post("/seed/thyroid-data")
async def seed_thyroid_data():
    """
    Quick endpoint to seed thyroid test data
    No request body needed - uses predefined thyroid tests and rules
    """
    try:
        # Predefined thyroid tests data
        thyroid_tests = BulkLabTestsRequest(
            individual_tests=[
                LabTestData(
                    name="Thyroid Stimulating Hormone (TSH)",
                    code="TSH",
                    description="Measures TSH levels to assess thyroid function. Primary screening test for thyroid disorders.",
                    type="test",
                    category="Blood Test",
                    sub_category="Endocrine Function",
                    sample_type="Blood",
                    requirements="No fasting required. Avoid biotin supplements 72 hours before test.",
                    procedure="Blood sample collected from arm vein",
                    price=250.0,
                    duration_minutes=15,
                    report_delivery_hours=24,
                    is_active=True,
                    is_home_collection_available=True,
                    reference_ranges='{"normal": "0.27-4.20 mIU/L", "units": "mIU/L"}',
                    units="mIU/L"
                ),
                LabTestData(
                    name="Free Thyroxine (Free T4)",
                    code="FT4",
                    description="Measures free T4 hormone levels. Essential for diagnosing thyroid dysfunction.",
                    type="test",
                    category="Blood Test",
                    sub_category="Endocrine Function",
                    sample_type="Blood",
                    requirements="No fasting required. Avoid biotin supplements 72 hours before test.",
                    procedure="Blood sample collected from arm vein",
                    price=300.0,
                    duration_minutes=15,
                    report_delivery_hours=24,
                    is_active=True,
                    is_home_collection_available=True,
                    reference_ranges='{"normal": "12-22 pmol/L", "units": "pmol/L"}',
                    units="pmol/L"
                ),
                LabTestData(
                    name="Free Triiodothyronine (Free T3)",
                    code="FT3",
                    description="Measures free T3 hormone levels. Helps evaluate thyroid function and hyperthyroid conditions.",
                    type="test",
                    category="Blood Test",
                    sub_category="Endocrine Function",
                    sample_type="Blood",
                    requirements="No fasting required. Avoid biotin supplements 72 hours before test.",
                    procedure="Blood sample collected from arm vein",
                    price=350.0,
                    duration_minutes=15,
                    report_delivery_hours=24,
                    is_active=True,
                    is_home_collection_available=True,
                    reference_ranges='{"normal": "3.1-6.8 pmol/L", "units": "pmol/L"}',
                    units="pmol/L"
                )
            ],
            test_panels=[
                LabTestData(
                    name="Thyroid Function Test (TFT) - Basic",
                    code="TFT-BASIC",
                    description="Basic thyroid function assessment including TSH and Free T4. Ideal for initial thyroid screening.",
                    type="panel",
                    tests_included=["TSH", "FT4"],  # Will be resolved to test_ids
                    category="Blood Test",
                    sub_category="Endocrine Panel",
                    sample_type="Blood",
                    requirements="No fasting required. Avoid biotin supplements 72 hours before test.",
                    procedure="Single blood sample collected from arm vein for all tests",
                    price=500.0,
                    duration_minutes=15,
                    report_delivery_hours=24,
                    is_active=True,
                    is_home_collection_available=True,
                    reference_ranges='{"included_tests": ["TSH", "FT4"]}',
                    units="Multiple"
                )
            ]
        )

        # Seed lab tests first
        lab_result = await seed_lab_tests(thyroid_tests)

        # Predefined AI rules
        thyroid_rules = BulkAIRulesRequest(
            rules=[
                AIRuleData(
                    name="Fatigue → TFT Basic",
                    description="Fatigue and tiredness are common symptoms of thyroid dysfunction",
                    symptoms=["fatigue", "tiredness", "exhaustion", "low energy", "feeling tired"],
                    synonyms=["worn out", "drained", "sluggish", "lethargy", "weakness"],
                    panel_code="TFT-BASIC",
                    weight=0.85,
                    rationale="Fatigue is one of the most common symptoms of both hypothyroidism and hyperthyroidism. A basic thyroid function test (TSH + Free T4) can help identify thyroid dysfunction as a potential cause.",
                    disclaimers=[
                        "Fatigue can have many causes beyond thyroid dysfunction",
                        "This test is for screening purposes only",
                        "Consult your healthcare provider for proper diagnosis"
                    ]
                ),
                AIRuleData(
                    name="Weight Gain → TFT Basic",
                    description="Unexplained weight gain can indicate hypothyroidism",
                    symptoms=["weight gain", "gaining weight", "increased weight", "putting on weight"],
                    synonyms=["weight increase", "getting heavier", "can't lose weight"],
                    panel_code="TFT-BASIC",
                    weight=0.80,
                    rationale="Unexplained weight gain is a classic symptom of hypothyroidism. Basic thyroid function testing can help identify if thyroid dysfunction is contributing to weight changes.",
                    disclaimers=[
                        "Weight gain can have multiple causes",
                        "Diet and exercise should be considered",
                        "Consult your healthcare provider for weight management"
                    ]
                )
            ]
        )

        # Seed AI rules
        rules_result = await seed_ai_rules(thyroid_rules)

        return {
            "success": True,
            "message": "Thyroid data seeded successfully",
            "lab_tests": lab_result,
            "ai_rules": rules_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thyroid data seeding failed: {str(e)}")


@router.get("/health")
async def admin_health_check():
    """Health check for admin endpoints"""
    return {
        "service": "admin_api",
        "status": "healthy",
        "endpoints": [
            "POST /seed/lab-tests - Bulk seed lab tests",
            "POST /seed/ai-rules - Bulk seed AI rules",
            "POST /seed/thyroid-data - Quick thyroid data seed",
            "POST /lab-tests - Create single test",
            "POST /ai-rules - Create single rule",
            "GET /lab-tests - Get all tests",
            "GET /ai-rules - Get all rules"
        ]
    }