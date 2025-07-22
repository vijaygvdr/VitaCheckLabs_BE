"""
Lab Tests API endpoints using DynamoDB
Replaces SQLAlchemy-based lab tests with DynamoDB
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.core.deps_dynamodb import get_current_active_user, get_admin_user
from app.services.dynamodb_service import lab_test_service
from app.schemas.lab_test import LabTestResponse, LabTestCreate, LabTestUpdate

router = APIRouter()

@router.get("/", response_model=List[LabTestResponse])
def get_lab_tests(
    is_active: bool = Query(True, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[int] = Query(None, description="Minimum price in paisa"),
    max_price: Optional[int] = Query(None, description="Maximum price in paisa"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get list of lab tests with optional filtering
    """
    try:
        if category:
            # Use category-price GSI for filtered search
            tests = lab_test_service.get_tests_by_category(
                category=category,
                min_price=min_price or 0,
                max_price=max_price or 99999999
            )
        else:
            # Get all tests and apply filters
            tests = lab_test_service.get_all_tests(is_active=is_active)
            
            # Apply price filtering if specified
            if min_price is not None or max_price is not None:
                filtered_tests = []
                for test in tests:
                    price = int(test.get('price', 0))
                    if (min_price is None or price >= min_price) and \
                       (max_price is None or price <= max_price):
                        filtered_tests.append(test)
                tests = filtered_tests
        
        # Convert to response format
        response_tests = []
        for test in tests:
            # Convert price from paisa to rupees for response and map test_id to id
            test_copy = test.copy()
            test_copy['price'] = float(test_copy.get('price', 0)) / 100
            test_copy['id'] = test_copy.get('test_id')
            response_tests.append(LabTestResponse(**test_copy))
        
        return response_tests
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch lab tests: {str(e)}"
        )

@router.get("/{test_id}", response_model=LabTestResponse)
def get_lab_test(
    test_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get specific lab test by ID
    """
    test = lab_test_service.get_test_by_id(test_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test not found"
        )
    
    # Convert price from paisa to rupees and map test_id to id
    test_copy = test.copy()
    test_copy['price'] = float(test_copy.get('price', 0)) / 100
    test_copy['id'] = test_copy.get('test_id')
    
    return LabTestResponse(**test_copy)

@router.get("/code/{code}", response_model=LabTestResponse)
def get_lab_test_by_code(
    code: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get specific lab test by code
    """
    test = lab_test_service.get_test_by_code(code)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test not found"
        )
    
    # Convert price from paisa to rupees and map test_id to id
    test_copy = test.copy()
    test_copy['price'] = float(test_copy.get('price', 0)) / 100
    test_copy['id'] = test_copy.get('test_id')
    
    return LabTestResponse(**test_copy)

@router.get("/categories/list")
def get_categories(current_user: dict = Depends(get_current_active_user)):
    """
    Get list of unique categories
    """
    try:
        tests = lab_test_service.get_all_tests(is_active=True)
        categories = list(set(test.get('category', '') for test in tests if test.get('category')))
        return {"categories": sorted(categories)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch categories: {str(e)}"
        )


# CRUD Operations (Admin only)
@router.post("/", response_model=LabTestResponse)
def create_lab_test(
    test_data: LabTestCreate,
    current_user: dict = Depends(get_admin_user)
):
    """
    Create a new lab test.
    Requires admin permissions.
    """
    try:
        # Check if test code already exists
        existing_test = lab_test_service.get_test_by_code(test_data.code)
        if existing_test:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lab test with code '{test_data.code}' already exists"
            )
        
        # Convert price to paisa for storage
        test_dict = test_data.model_dump()
        test_dict['price'] = int(float(test_dict['price']) * 100)
        test_dict['created_by'] = current_user.get('username', 'admin')
        
        # Create the test
        created_test = lab_test_service.create_test(test_dict)
        
        # Convert price back to rupees for response and map test_id to id
        created_test['price'] = float(created_test.get('price', 0)) / 100
        created_test['id'] = created_test.get('test_id')
        
        return LabTestResponse(**created_test)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create lab test: {str(e)}"
        )


@router.put("/{test_id}", response_model=LabTestResponse)
def update_lab_test(
    test_id: str,
    test_data: LabTestUpdate,
    current_user: dict = Depends(get_admin_user)
):
    """
    Update an existing lab test.
    Requires admin permissions.
    """
    try:
        # Check if test exists
        existing_test = lab_test_service.get_test_by_id(test_id)
        if not existing_test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lab test not found"
            )
        
        # Prepare update data
        update_dict = test_data.model_dump(exclude_unset=True)
        
        # Convert price to paisa if provided
        if 'price' in update_dict:
            update_dict['price'] = int(float(update_dict['price']) * 100)
        
        update_dict['updated_by'] = current_user.get('username', 'admin')
        
        # Update the test
        updated_test = lab_test_service.update_test(test_id, update_dict)
        
        # Convert price back to rupees for response and map test_id to id
        updated_test['price'] = float(updated_test.get('price', 0)) / 100
        updated_test['id'] = updated_test.get('test_id')
        
        return LabTestResponse(**updated_test)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update lab test: {str(e)}"
        )


@router.delete("/{test_id}")
def delete_lab_test(
    test_id: str,
    current_user: dict = Depends(get_admin_user)
):
    """
    Delete a lab test (soft delete by setting is_active=False).
    Requires admin permissions.
    """
    try:
        # Check if test exists
        existing_test = lab_test_service.get_test_by_id(test_id)
        if not existing_test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lab test not found"
            )
        
        # Soft delete by setting is_active=False
        lab_test_service.update_test(test_id, {
            'is_active': False,
            'updated_by': current_user.get('username', 'admin')
        })
        
        return {"message": f"Lab test '{existing_test.get('name')}' has been deactivated"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete lab test: {str(e)}"
        )


@router.post("/{test_id}/book")
def book_lab_test(
    test_id: str,
    booking_data: dict,  # We'll use the booking schema from bookings_dynamodb
    current_user: dict = Depends(get_current_active_user)
):
    """
    Book a lab test.
    This is a convenience endpoint that redirects to the booking service.
    """
    try:
        # Check if test exists and is active
        test = lab_test_service.get_test_by_id(test_id)
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lab test not found"
            )
        
        if not test.get('is_active', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lab test is not available for booking"
            )
        
        # Import booking service to create booking
        from app.services.dynamodb_service import booking_service
        
        # Add test_id to booking data
        booking_data['test_id'] = test_id
        booking_data['user_id'] = current_user.get('id')
        
        # Create the booking
        booking = booking_service.create_booking(booking_data)
        
        return {
            "message": "Lab test booked successfully",
            "booking_id": booking.get('id'),
            "booking_reference": booking.get('booking_reference'),
            "test_name": test.get('name'),
            "test_code": test.get('code')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to book lab test: {str(e)}"
        )


@router.get("/stats/overview")
def get_lab_test_stats(
    current_user: dict = Depends(get_admin_user)
):
    """
    Get lab test statistics overview.
    Requires admin permissions.
    """
    try:
        # Get all tests
        all_tests = lab_test_service.get_all_tests(is_active=None)  # Get both active and inactive
        
        # Calculate statistics
        total_tests = len(all_tests)
        active_tests = len([t for t in all_tests if t.get('is_active', False)])
        inactive_tests = total_tests - active_tests
        
        # Category breakdown
        category_counts = {}
        for test in all_tests:
            if test.get('is_active', False):  # Only count active tests
                category = test.get('category', 'Other')
                category_counts[category] = category_counts.get(category, 0) + 1
        
        # Price statistics (convert from paisa to rupees)
        active_prices = [float(t.get('price', 0)) / 100 for t in all_tests if t.get('is_active', False)]
        
        price_stats = {}
        if active_prices:
            price_stats = {
                "min_price": min(active_prices),
                "max_price": max(active_prices),
                "avg_price": round(sum(active_prices) / len(active_prices), 2)
            }
        
        # Home collection availability
        home_collection_available = len([
            t for t in all_tests 
            if t.get('is_active', False) and t.get('is_home_collection_available', False)
        ])
        
        return {
            "total_tests": total_tests,
            "active_tests": active_tests,
            "inactive_tests": inactive_tests,
            "home_collection_available": home_collection_available,
            "category_breakdown": category_counts,
            "price_statistics": price_stats,
            "most_popular_category": max(category_counts.items(), key=lambda x: x[1])[0] if category_counts else None
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch lab test statistics: {str(e)}"
        )