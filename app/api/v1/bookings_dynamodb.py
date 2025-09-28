"""
Bookings API endpoints using DynamoDB
Replaces SQLAlchemy-based bookings with DynamoDB
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from datetime import datetime, timedelta
from app.core.deps_dynamodb import get_current_active_user, get_admin_user
from app.services.dynamodb_service import booking_service, lab_test_service
from app.schemas.booking import BookingCreate, BookingResponse, BookingUpdate, BookingStatusUpdate, BookingAdminUpdate

router = APIRouter()

@router.post("/{test_id}", response_model=BookingResponse)
def create_booking(
    test_id: str,
    booking_data: BookingCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Create a new booking for a specific test
    """
    # Verify lab test exists
    lab_test = lab_test_service.get_test_by_id(test_id)
    if not lab_test:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Lab test not found"
        )
    
    if not lab_test.get('is_active', False):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Lab test is not available"
        )
    
    # Check if home collection is requested but not available
    if booking_data.home_collection and not lab_test.get('is_home_collection_available', False):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Home collection is not available for this test"
        )
    
    # Validate appointment date (must be in future)
    from datetime import timezone
    now = datetime.now(timezone.utc)
    appointment_dt = booking_data.appointment_date
    
    # Handle timezone-aware/naive datetime comparison
    if appointment_dt.tzinfo is None:
        # If appointment date is naive, assume UTC
        appointment_dt = appointment_dt.replace(tzinfo=timezone.utc)
    elif now.tzinfo is None:
        # If now is naive, make it timezone-aware
        now = now.replace(tzinfo=timezone.utc)
    
    if appointment_dt <= now:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Appointment date must be in the future"
        )
    
    # Create booking
    booking_dict = {
        'user_id': current_user.get('id') or current_user.get('user_id'),
        'test_id': test_id,
        'patient_name': booking_data.patient_name,
        'patient_age': booking_data.patient_age,
        'patient_gender': booking_data.patient_gender,
        'appointment_date': booking_data.appointment_date,
        'home_collection': booking_data.home_collection,
        'address': booking_data.address or '',
        'phone_number': booking_data.phone_number,
        'special_instructions': booking_data.special_instructions or '',
        'status': 'pending'
    }
    
    try:
        created_booking = booking_service.create_booking(booking_dict)
        
        # Get related test data
        test_data = lab_test_service.get_test_by_id(created_booking.get('test_id'))
        if test_data:
            test_data = test_data.copy()
            test_data['price'] = float(test_data.get('price', 0)) / 100
            test_data['id'] = test_data.get('test_id')
        
        # Convert booking format and map booking_id to id
        booking_copy = created_booking.copy()
        booking_copy['id'] = booking_copy.get('booking_id')
        
        # Fix status enum case and empty datetime fields
        booking_copy['status'] = booking_copy.get('status', 'pending').lower()
        
        # Convert empty strings to None for optional datetime fields
        for field in ['cancelled_at', 'completed_at']:
            if booking_copy.get(field) == '':
                booking_copy[field] = None
        
        # Ensure all optional fields are present
        booking_copy.setdefault('admin_notes', None)
        booking_copy.setdefault('cancellation_reason', None)
        booking_copy.setdefault('cancelled_at', None)
        booking_copy.setdefault('completed_at', None)
        
        # Fix datetime format - remove Z suffix if timezone is already present
        for dt_field in ['appointment_date', 'created_at', 'updated_at']:
            if booking_copy.get(dt_field) and isinstance(booking_copy[dt_field], str):
                dt_str = booking_copy[dt_field]
                # If datetime has timezone and ends with Z, remove the Z
                if '+' in dt_str and dt_str.endswith('Z'):
                    booking_copy[dt_field] = dt_str[:-1]
        
        # Create response with nested objects
        from app.schemas.lab_test import LabTestResponse
        from app.schemas.auth import UserResponse
        
        booking_response_data = {
            **booking_copy,
            'test': LabTestResponse(**test_data) if test_data else None,
            'user': UserResponse(
                id=current_user.get('user_id'),
                email=current_user.get('email', ''),
                username=current_user.get('username', ''),
                role=current_user.get('role', 'user').lower(),
                is_active=current_user.get('is_active', True),
                is_verified=current_user.get('is_verified', False),
                created_at=current_user.get('created_at', '2025-01-01T00:00:00Z')
            )
        }
        
        return BookingResponse(**booking_response_data)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create booking: {str(e)}"
        )

@router.get("/my", response_model=List[BookingResponse])
def get_my_bookings(
    booking_status: Optional[str] = Query(None, description="Filter by status"),
    upcoming_only: bool = Query(False, description="Show only upcoming bookings"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get current user's bookings
    """
    try:
        # Get current user ID - handle both 'id' and 'user_id' fields
        user_id = current_user.get('id') or current_user.get('user_id')
        if not user_id:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="User ID not found in authentication token"
            )

        # Get bookings from today onwards if upcoming_only is True
        date_from = datetime.utcnow() if upcoming_only else None
        bookings = booking_service.get_user_bookings(user_id, date_from)

        # If no bookings found for this user, return empty list
        if not bookings:
            return []

        # Filter by status if provided
        if booking_status:
            bookings = [b for b in bookings if b.get('status') == booking_status]

        # Convert bookings to response format
        response_bookings = []
        for booking in bookings:
            # Get related test data
            test_data = lab_test_service.get_test_by_id(booking.get('test_id'))
            # Convert test data format and map test_id to id
            if test_data:
                test_data = test_data.copy()
                test_data['price'] = float(test_data.get('price', 0)) / 100
                test_data['id'] = test_data.get('test_id')
            
            # Convert booking format and ensure id field exists
            booking_copy = booking.copy()
            # If booking_id exists, use it as id, otherwise keep existing id
            if 'booking_id' in booking_copy:
                booking_copy['id'] = booking_copy['booking_id']
            elif 'id' not in booking_copy:
                # If neither id nor booking_id exist, this is an error
                raise ValueError("Booking record missing both 'id' and 'booking_id' fields")
            
            # Fix status enum case and empty datetime fields
            booking_copy['status'] = booking_copy.get('status', 'pending').lower()
            
            # Convert empty strings to None for optional datetime fields
            for field in ['cancelled_at', 'completed_at']:
                if booking_copy.get(field) == '':
                    booking_copy[field] = None
            
            # Ensure all optional fields are present
            booking_copy.setdefault('admin_notes', None)
            booking_copy.setdefault('cancellation_reason', None)
            booking_copy.setdefault('cancelled_at', None)
            booking_copy.setdefault('completed_at', None)
            
            # Fix datetime format - remove Z suffix if timezone is already present
            for dt_field in ['appointment_date', 'created_at', 'updated_at']:
                if booking_copy.get(dt_field) and isinstance(booking_copy[dt_field], str):
                    dt_str = booking_copy[dt_field]
                    # If datetime has timezone and ends with Z, remove the Z
                    if '+' in dt_str and dt_str.endswith('Z'):
                        booking_copy[dt_field] = dt_str[:-1]
            
            # Create nested objects
            from app.schemas.lab_test import LabTestResponse
            from app.schemas.auth import UserResponse
            
            booking_response_data = {
                **booking_copy,
                'test': LabTestResponse(**test_data) if test_data else None,
                'user': UserResponse(
                id=user_id,
                email=current_user.get('email', ''),
                username=current_user.get('username', ''),
                role=current_user.get('role', 'user').lower(),
                is_active=current_user.get('is_active', True),
                is_verified=current_user.get('is_verified', False),
                created_at=current_user.get('created_at', '2025-01-01T00:00:00Z')
            )
            }
            
            response_bookings.append(BookingResponse(**booking_response_data))
        
        return response_bookings
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bookings: {str(e)}"
        )

@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(
    booking_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get specific booking by ID
    """
    booking = booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Check if user owns this booking or is admin
    current_user_id = current_user.get('id') or current_user.get('user_id')
    if booking['user_id'] != current_user_id and current_user.get('role') != 'ADMIN':
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this booking"
        )
    
    return BookingResponse(**booking)

@router.get("/reference/{reference}", response_model=BookingResponse)
def get_booking_by_reference(
    reference: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get booking by reference number
    """
    booking = booking_service.get_booking_by_reference(reference)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Check if user owns this booking or is admin
    current_user_id = current_user.get('id') or current_user.get('user_id')
    if booking['user_id'] != current_user_id and current_user.get('role') != 'ADMIN':
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this booking"
        )
    
    return BookingResponse(**booking)

@router.put("/{booking_id}", response_model=BookingResponse)
def update_booking(
    booking_id: str,
    booking_update: BookingUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update booking details
    """
    # Get existing booking
    booking = booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Check if user owns this booking or is admin
    current_user_id = current_user.get('id') or current_user.get('user_id')
    if booking['user_id'] != current_user_id and current_user.get('role') != 'ADMIN':
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this booking"
        )
    
    # Check if booking can be modified
    if booking.get('status') not in ['pending']:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Booking cannot be modified in current status"
        )
    
    # Prepare updates
    updates = {}
    if booking_update.appointment_date is not None:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        appointment_dt = booking_update.appointment_date
        
        # Handle timezone-aware/naive datetime comparison
        if appointment_dt.tzinfo is None:
            # If appointment date is naive, assume UTC
            appointment_dt = appointment_dt.replace(tzinfo=timezone.utc)
        elif now.tzinfo is None:
            # If now is naive, make it timezone-aware
            now = now.replace(tzinfo=timezone.utc)
        
        if appointment_dt <= now:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="Appointment date must be in the future"
            )
        updates['appointment_date'] = booking_update.appointment_date.isoformat() + 'Z'
    
    if booking_update.address is not None:
        updates['address'] = booking_update.address
    if booking_update.special_instructions is not None:
        updates['special_instructions'] = booking_update.special_instructions
    if booking_update.phone_number is not None:
        updates['phone_number'] = booking_update.phone_number
    
    if updates:
        success = booking_service.update_booking(booking_id, updates)
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update booking"
            )
    
    # Get updated booking
    updated_booking = booking_service.get_booking_by_id(booking_id)
    return BookingResponse(**updated_booking)

@router.put("/{booking_id}/cancel")
def cancel_booking(
    booking_id: str,
    reason: str = Query(..., description="Cancellation reason"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Cancel a booking
    """
    # Get existing booking
    booking = booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Check if user owns this booking or is admin
    current_user_id = current_user.get('id') or current_user.get('user_id')
    if booking['user_id'] != current_user_id and current_user.get('role') != 'ADMIN':
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this booking"
        )
    
    # Check if booking can be cancelled
    if booking.get('status') not in ['pending', 'confirmed']:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Booking cannot be cancelled in current status"
        )
    
    # Update booking status
    updates = {
        'status': 'cancelled',
        'cancellation_reason': reason,
        'cancelled_at': datetime.utcnow().isoformat() + 'Z'
    }
    
    success = booking_service.update_booking(booking_id, updates)
    if not success:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel booking"
        )
    
    return {"message": "Booking cancelled successfully"}

# Admin endpoints
@router.get("/admin/all", response_model=List[BookingResponse])
def get_all_bookings(
    booking_status: Optional[str] = Query(None, description="Filter by status"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    current_user: dict = Depends(get_admin_user)
):
    """
    Get all bookings (admin only)
    """
    try:
        # For admin view, we'd need to scan the table or use a different approach
        # This is a simplified implementation
        from app.services.dynamodb_service import DynamoDBService
        db_service = DynamoDBService()
        
        # Scan all bookings (not ideal for large datasets)
        response = db_service.bookings_table.scan()
        bookings = response.get('Items', [])
        
        # Apply filters
        if booking_status:
            bookings = [b for b in bookings if b.get('status') == booking_status]
        
        if date_from:
            date_str = date_from.isoformat() + 'Z'
            bookings = [b for b in bookings if b.get('appointment_date', '') >= date_str]
        
        # Sort by appointment date
        bookings.sort(key=lambda x: x.get('appointment_date', ''))
        
        return [BookingResponse(**booking) for booking in bookings]
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bookings: {str(e)}"
        )

@router.put("/{booking_id}/status", response_model=BookingResponse)
def update_booking_status(
    booking_id: str,
    status_update: BookingStatusUpdate,
    current_user: dict = Depends(get_admin_user)
):
    """
    Update booking status (admin only)
    """
    # Get existing booking
    booking = booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Prepare status update
    updates = {
        'status': status_update.status.value,
        'admin_notes': status_update.admin_notes or '',
        'updated_by': current_user.get('username', 'admin')
    }
    
    # Add completion timestamp if status is completed
    if status_update.status.value == 'completed':
        updates['completed_at'] = datetime.utcnow().isoformat() + 'Z'
    
    success = booking_service.update_booking(booking_id, updates)
    if not success:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update booking status"
        )
    
    # Get updated booking
    updated_booking = booking_service.get_booking_by_id(booking_id)
    return BookingResponse(**updated_booking)

@router.put("/{booking_id}/admin", response_model=BookingResponse)
def admin_update_booking(
    booking_id: str,
    booking_update: BookingAdminUpdate,
    current_user: dict = Depends(get_admin_user)
):
    """
    Admin update booking with advanced permissions
    """
    # Get existing booking
    booking = booking_service.get_booking_by_id(booking_id)
    if not booking:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    # Prepare updates
    updates = {}
    if booking_update.status is not None:
        updates['status'] = booking_update.status.value
        # Add completion timestamp if status is completed
        if booking_update.status.value == 'completed':
            updates['completed_at'] = datetime.utcnow().isoformat() + 'Z'
    
    if booking_update.admin_notes is not None:
        updates['admin_notes'] = booking_update.admin_notes
    
    if booking_update.appointment_date is not None:
        updates['appointment_date'] = booking_update.appointment_date.isoformat() + 'Z'
    
    updates['updated_by'] = current_user.get('username', 'admin')
    
    if updates:
        success = booking_service.update_booking(booking_id, updates)
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update booking"
            )
    
    # Get updated booking
    updated_booking = booking_service.get_booking_by_id(booking_id)
    return BookingResponse(**updated_booking)

@router.get("/admin/stats", response_model=dict)
def get_booking_statistics(
    current_user: dict = Depends(get_admin_user)
):
    """
    Get booking statistics (admin only)
    """
    try:
        from app.services.dynamodb_service import DynamoDBService
        db_service = DynamoDBService()
        
        # Scan all bookings
        response = db_service.bookings_table.scan()
        bookings = response.get('Items', [])
        
        # Calculate statistics
        total_bookings = len(bookings)
        
        # Status breakdown
        status_counts = {}
        for booking in bookings:
            status = booking.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Today's bookings
        today = datetime.utcnow().date()
        today_str = today.isoformat()
        today_bookings = len([
            b for b in bookings 
            if b.get('appointment_date', '').startswith(today_str)
        ])
        
        # Upcoming bookings (from tomorrow onwards)
        tomorrow = today + timedelta(days=1)
        upcoming_bookings = len([
            b for b in bookings 
            if b.get('appointment_date', '') >= tomorrow.isoformat() and 
               b.get('status') not in ['cancelled', 'completed', 'no_show']
        ])
        
        # Home collection statistics
        home_collection_bookings = len([
            b for b in bookings if b.get('home_collection', False)
        ])
        
        return {
            "total_bookings": total_bookings,
            "pending_bookings": status_counts.get('pending', 0),
            "confirmed_bookings": status_counts.get('confirmed', 0),
            "completed_bookings": status_counts.get('completed', 0),
            "cancelled_bookings": status_counts.get('cancelled', 0),
            "no_show_bookings": status_counts.get('no_show', 0),
            "today_bookings": today_bookings,
            "upcoming_bookings": upcoming_bookings,
            "home_collection_bookings": home_collection_bookings,
            "status_breakdown": status_counts
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch booking statistics: {str(e)}"
        )