from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from app.database import get_db
from app.core.deps import get_current_active_user, get_admin_user, get_optional_user
from app.models.user import User
from app.models.lab_test import LabTest
from app.schemas.lab_test import (
    LabTestCreate, LabTestUpdate, LabTestResponse, LabTestListResponse,
    LabTestFilter, LabTestCategoryResponse, LabTestBooking, LabTestBookingResponse,
    LabTestStats, LabTestCategory, SampleType
)

router = APIRouter()


@router.get("/", response_model=LabTestListResponse)
async def get_lab_tests(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[LabTestCategory] = Query(None, description="Filter by category"),
    sample_type: Optional[SampleType] = Query(None, description="Filter by sample type"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_home_collection_available: Optional[bool] = Query(None, description="Filter by home collection"),
    search: Optional[str] = Query(None, min_length=1, description="Search in name and description"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get list of lab tests with filtering and pagination.
    Public endpoint - no authentication required.
    """
    # Build query
    query = db.query(LabTest)
    
    # Apply filters
    if category:
        query = query.filter(LabTest.category == category.value)
    
    if sample_type:
        query = query.filter(LabTest.sample_type == sample_type.value)
    
    if min_price is not None:
        query = query.filter(LabTest.price >= min_price)
    
    if max_price is not None:
        query = query.filter(LabTest.price <= max_price)
    
    if is_active is not None:
        query = query.filter(LabTest.is_active == is_active)
    else:
        # For public access, only show active tests by default
        if current_user is None or not current_user.is_admin():
            query = query.filter(LabTest.is_active == True)
    
    if is_home_collection_available is not None:
        query = query.filter(LabTest.is_home_collection_available == is_home_collection_available)
    
    if search:
        search_filter = or_(
            LabTest.name.ilike(f"%{search}%"),
            LabTest.description.ilike(f"%{search}%"),
            LabTest.code.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    tests = query.offset(offset).limit(per_page).all()
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    return LabTestListResponse(
        tests=tests,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{test_id}", response_model=LabTestResponse)
async def get_lab_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get a specific lab test by ID.
    Public endpoint - no authentication required.
    """
    test = db.query(LabTest).filter(LabTest.id == test_id).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test not found"
        )
    
    # For public access, only show active tests
    if current_user is None or not current_user.is_admin():
        if not test.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lab test not found"
            )
    
    return test


@router.post("/", response_model=LabTestResponse, status_code=status.HTTP_201_CREATED)
async def create_lab_test(
    test_data: LabTestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Create a new lab test.
    Requires admin permissions.
    """
    # Check if test code already exists
    existing_test = db.query(LabTest).filter(LabTest.code == test_data.code).first()
    if existing_test:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Test code already exists"
        )
    
    # Create new lab test
    test = LabTest(**test_data.model_dump())
    db.add(test)
    db.commit()
    db.refresh(test)
    
    return test


@router.put("/{test_id}", response_model=LabTestResponse)
async def update_lab_test(
    test_id: int,
    test_data: LabTestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Update a lab test.
    Requires admin permissions.
    """
    test = db.query(LabTest).filter(LabTest.id == test_id).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test not found"
        )
    
    # Update only provided fields
    update_data = test_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(test, field, value)
    
    db.commit()
    db.refresh(test)
    
    return test


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lab_test(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Delete a lab test.
    Requires admin permissions.
    """
    test = db.query(LabTest).filter(LabTest.id == test_id).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test not found"
        )
    
    db.delete(test)
    db.commit()


@router.get("/categories/list", response_model=List[LabTestCategoryResponse])
async def get_test_categories(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get list of test categories with counts.
    Public endpoint - no authentication required.
    """
    # Base query for active tests (for public access)
    base_query = db.query(LabTest)
    if current_user is None or not current_user.is_admin():
        base_query = base_query.filter(LabTest.is_active == True)
    
    # Get categories with counts
    categories = (
        base_query
        .with_entities(
            LabTest.category,
            func.count(LabTest.id).label('count')
        )
        .group_by(LabTest.category)
        .all()
    )
    
    result = []
    for category, count in categories:
        # Get sub-categories for this category
        sub_categories_query = (
            base_query
            .filter(LabTest.category == category)
            .filter(LabTest.sub_category.isnot(None))
            .with_entities(func.distinct(LabTest.sub_category))
            .all()
        )
        
        sub_categories = [sc[0] for sc in sub_categories_query if sc[0] is not None]
        
        result.append(LabTestCategoryResponse(
            category=category,
            count=count,
            sub_categories=sub_categories
        ))
    
    return result


@router.post("/{test_id}/book", response_model=LabTestBookingResponse, status_code=status.HTTP_201_CREATED)
async def book_lab_test(
    test_id: int,
    booking_data: LabTestBooking,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Book a lab test.
    Requires authentication.
    """
    # Verify test exists and is active
    test = db.query(LabTest).filter(
        LabTest.id == test_id,
        LabTest.is_active == True
    ).first()
    
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test not found or inactive"
        )
    
    # Validate age requirements
    if not test.is_available_for_age(booking_data.patient_age):
        age_msg = f"Test age requirements: "
        if test.minimum_age and test.maximum_age:
            age_msg += f"{test.minimum_age}-{test.maximum_age} years"
        elif test.minimum_age:
            age_msg += f"minimum {test.minimum_age} years"
        elif test.maximum_age:
            age_msg += f"maximum {test.maximum_age} years"
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patient age ({booking_data.patient_age}) does not meet test requirements. {age_msg}"
        )
    
    # Validate home collection request
    if booking_data.home_collection and not test.is_home_collection_available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Home collection is not available for this test"
        )
    
    # For this implementation, we'll create a simple booking record
    # In a real system, this would involve creating a booking in a separate bookings table
    booking_response = LabTestBookingResponse(
        id=1,  # This would be generated from the bookings table
        test=test,
        patient_name=booking_data.patient_name,
        patient_age=booking_data.patient_age,
        patient_gender=booking_data.patient_gender,
        appointment_date=booking_data.appointment_date,
        home_collection=booking_data.home_collection,
        address=booking_data.address,
        phone_number=booking_data.phone_number,
        special_instructions=booking_data.special_instructions,
        booking_status="confirmed",
        created_at=func.now()
    )
    
    return booking_response


@router.get("/stats/overview", response_model=LabTestStats)
async def get_lab_test_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Get lab test statistics.
    Requires admin permissions.
    """
    # Get basic stats
    total_tests = db.query(LabTest).count()
    active_tests = db.query(LabTest).filter(LabTest.is_active == True).count()
    categories_count = db.query(func.distinct(LabTest.category)).count()
    home_collection_available = db.query(LabTest).filter(
        LabTest.is_home_collection_available == True,
        LabTest.is_active == True
    ).count()
    
    # Get average price
    avg_price_result = db.query(func.avg(LabTest.price)).filter(LabTest.is_active == True).scalar()
    average_price = avg_price_result or 0
    
    # Get most popular category (by count)
    most_popular = (
        db.query(LabTest.category, func.count(LabTest.id))
        .filter(LabTest.is_active == True)
        .group_by(LabTest.category)
        .order_by(func.count(LabTest.id).desc())
        .first()
    )
    
    most_popular_category = most_popular[0] if most_popular else "N/A"
    
    return LabTestStats(
        total_tests=total_tests,
        active_tests=active_tests,
        categories_count=categories_count,
        average_price=average_price,
        most_popular_category=most_popular_category,
        home_collection_available=home_collection_available
    )