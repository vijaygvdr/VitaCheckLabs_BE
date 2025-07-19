from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_active_user, get_admin_user
from app.models.user import User
from app.models.booking import Booking, BookingStatus
from app.services.booking_service import BookingService
from app.schemas.booking import (
    BookingResponse,
    BookingCancellation,
    BookingStatusUpdate,
    BookingAdminUpdate
)

router = APIRouter(prefix="/bookings", tags=["Booking Management"])


@router.get("/my", response_model=dict)
def get_my_bookings(
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    home_collection: Optional[bool] = Query(None, description="Filter by home collection"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's bookings with filtering and pagination
    
    - **status**: Filter by booking status (pending, confirmed, cancelled, completed, no_show)
    - **date_from**: Filter bookings from this date
    - **date_to**: Filter bookings until this date
    - **home_collection**: Filter by home collection requirement
    - **page**: Page number for pagination
    - **size**: Number of items per page
    """
    booking_service = BookingService(db)
    
    # Parse dates if provided
    date_from_obj = None
    date_to_obj = None
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use YYYY-MM-DD"
            )
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use YYYY-MM-DD"
            )
    
    from app.schemas.booking import BookingFilterParams
    filters = BookingFilterParams(
        status=status,
        date_from=date_from_obj,
        date_to=date_to_obj,
        home_collection=home_collection,
        page=page,
        size=size
    )
    
    result = booking_service.get_user_bookings(current_user.id, filters)
    
    # Convert to response format
    bookings_response = []
    for booking in result["bookings"]:
        booking_dict = {
            "id": booking.id,
            "booking_reference": booking.booking_reference,
            "patient_name": booking.patient_name,
            "patient_age": booking.patient_age,
            "appointment_date": booking.appointment_date,
            "status": booking.status,
            "home_collection": booking.home_collection,
            "created_at": booking.created_at,
            "test_name": booking.test.name,
            "test_code": booking.test.code,
            "test_price": float(booking.test.price),
            "user_email": booking.user.email,
            "user_name": booking.user.full_name
        }
        bookings_response.append(booking_dict)
    
    return {
        "bookings": bookings_response,
        "pagination": {
            "total": result["total"],
            "page": result["page"],
            "size": result["size"],
            "total_pages": result["total_pages"]
        }
    }


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get specific booking details by ID
    
    Users can only access their own bookings.
    """
    booking_service = BookingService(db)
    booking = booking_service.get_booking_by_id(booking_id, current_user.id)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking


@router.get("/reference/{booking_reference}", response_model=BookingResponse)
def get_booking_by_reference(
    booking_reference: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get specific booking details by booking reference
    
    Users can only access their own bookings.
    """
    booking_service = BookingService(db)
    booking = booking_service.get_booking_by_reference(booking_reference, current_user.id)
    
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    return booking


@router.put("/{booking_id}/cancel")
def cancel_booking(
    booking_id: int,
    cancellation: BookingCancellation,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Cancel a booking
    
    Users can only cancel their own bookings if they are in pending or confirmed status
    and the appointment date is in the future.
    """
    booking_service = BookingService(db)
    booking = booking_service.cancel_booking(
        booking_id, 
        cancellation.cancellation_reason, 
        current_user.id
    )
    
    return {
        "message": "Booking cancelled successfully",
        "booking_reference": booking.booking_reference,
        "status": booking.status.value
    }


# Admin endpoints
@router.get("/", response_model=dict, dependencies=[Depends(get_admin_user)])
def get_all_bookings(
    status: Optional[BookingStatus] = Query(None, description="Filter by booking status"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    test_id: Optional[int] = Query(None, description="Filter by test ID"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    home_collection: Optional[bool] = Query(None, description="Filter by home collection"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db)
):
    """
    Get all bookings with filtering and pagination (Admin only)
    
    Allows administrators to view and manage all bookings in the system.
    """
    booking_service = BookingService(db)
    
    # Parse dates if provided
    date_from_obj = None
    date_to_obj = None
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_from format. Use YYYY-MM-DD"
            )
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date_to format. Use YYYY-MM-DD"
            )
    
    from app.schemas.booking import BookingFilterParams
    filters = BookingFilterParams(
        status=status,
        user_id=user_id,
        test_id=test_id,
        date_from=date_from_obj,
        date_to=date_to_obj,
        home_collection=home_collection,
        page=page,
        size=size
    )
    
    result = booking_service.get_all_bookings(filters)
    
    # Convert to response format
    bookings_response = []
    for booking in result["bookings"]:
        booking_dict = {
            "id": booking.id,
            "booking_reference": booking.booking_reference,
            "patient_name": booking.patient_name,
            "patient_age": booking.patient_age,
            "appointment_date": booking.appointment_date,
            "status": booking.status,
            "home_collection": booking.home_collection,
            "created_at": booking.created_at,
            "test_name": booking.test.name,
            "test_code": booking.test.code,
            "test_price": float(booking.test.price),
            "user_email": booking.user.email,
            "user_name": booking.user.full_name
        }
        bookings_response.append(booking_dict)
    
    return {
        "bookings": bookings_response,
        "pagination": {
            "total": result["total"],
            "page": result["page"],
            "size": result["size"],
            "total_pages": result["total_pages"]
        }
    }


@router.put("/{booking_id}/status", dependencies=[Depends(get_admin_user)])
def update_booking_status(
    booking_id: int,
    status_update: BookingStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Update booking status (Admin only)
    
    Allows administrators to change booking status and add admin notes.
    Can be used to mark bookings as COMPLETED.
    """
    booking_service = BookingService(db)
    booking = booking_service.update_booking_status(booking_id, status_update)
    
    return {
        "message": "Booking status updated successfully",
        "booking_reference": booking.booking_reference,
        "status": booking.status.value,
        "updated_at": booking.updated_at
    }


@router.put("/{booking_id}/admin", dependencies=[Depends(get_admin_user)])
def admin_update_booking(
    booking_id: int,
    update_data: BookingAdminUpdate,
    db: Session = Depends(get_db)
):
    """
    Admin update booking (Admin only)
    
    Allows administrators to update various booking fields including status,
    admin notes, and appointment date.
    """
    booking_service = BookingService(db)
    booking = booking_service.admin_update_booking(booking_id, update_data)
    
    return {
        "message": "Booking updated successfully",
        "booking_reference": booking.booking_reference,
        "status": booking.status.value,
        "updated_at": booking.updated_at
    }