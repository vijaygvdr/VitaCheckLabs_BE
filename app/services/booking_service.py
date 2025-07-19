from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from fastapi import HTTPException, status

from app.models.booking import Booking, BookingStatus
from app.models.lab_test import LabTest
from app.models.user import User
from app.schemas.booking import (
    BookingCreate, 
    BookingResponse, 
    BookingListResponse, 
    BookingFilterParams,
    BookingStatsResponse,
    BookingStatusUpdate,
    BookingAdminUpdate
)


class BookingService:
    """Service class for handling booking business logic"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_booking(self, user_id: int, test_id: int, booking_data: BookingCreate) -> Booking:
        """Create a new booking with validation"""
        
        # Validate test exists and is active
        test = self.db.query(LabTest).filter(
            LabTest.id == test_id,
            LabTest.is_active == True
        ).first()
        
        if not test:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lab test not found or inactive"
            )
        
        # Validate user exists and is active
        user = self.db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or inactive"
            )
        
        # Validate age restrictions
        if not test.is_available_for_age(booking_data.patient_age):
            min_age = test.minimum_age or 0
            max_age = test.maximum_age or 120
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Patient age {booking_data.patient_age} is not within allowed range ({min_age}-{max_age}) for this test"
            )
        
        # Validate home collection
        if booking_data.home_collection and not test.is_home_collection_available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Home collection is not available for this test"
            )
        
        # Validate appointment date is in future
        if booking_data.appointment_date <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment date must be in the future"
            )
        
        # Create booking
        booking = Booking(
            test_id=test_id,
            user_id=user_id,
            patient_name=booking_data.patient_name,
            patient_age=booking_data.patient_age,
            patient_gender=booking_data.patient_gender,
            appointment_date=booking_data.appointment_date,
            home_collection=booking_data.home_collection,
            address=booking_data.address,
            phone_number=booking_data.phone_number,
            special_instructions=booking_data.special_instructions,
            status=BookingStatus.PENDING
        )
        
        self.db.add(booking)
        self.db.commit()
        self.db.refresh(booking)
        
        # Ensure relationships are loaded
        booking = self.db.query(Booking).options(
            joinedload(Booking.test),
            joinedload(Booking.user)
        ).filter(Booking.id == booking.id).first()
        
        return booking
    
    def get_booking_by_id(self, booking_id: int, user_id: Optional[int] = None) -> Optional[Booking]:
        """Get booking by ID with optional user filtering"""
        query = self.db.query(Booking).options(
            joinedload(Booking.test),
            joinedload(Booking.user)
        ).filter(Booking.id == booking_id)
        
        if user_id:
            query = query.filter(Booking.user_id == user_id)
        
        return query.first()
    
    def get_booking_by_reference(self, reference: str, user_id: Optional[int] = None) -> Optional[Booking]:
        """Get booking by reference with optional user filtering"""
        query = self.db.query(Booking).options(
            joinedload(Booking.test),
            joinedload(Booking.user)
        ).filter(Booking.booking_reference == reference)
        
        if user_id:
            query = query.filter(Booking.user_id == user_id)
        
        return query.first()
    
    def get_user_bookings(
        self, 
        user_id: int, 
        filters: Optional[BookingFilterParams] = None
    ) -> Dict[str, Any]:
        """Get user's bookings with filtering and pagination"""
        
        query = self.db.query(Booking).options(
            joinedload(Booking.test),
            joinedload(Booking.user)
        ).filter(Booking.user_id == user_id)
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and sorting
        if filters:
            offset = (filters.page - 1) * filters.size
            query = query.order_by(desc(Booking.created_at)).offset(offset).limit(filters.size)
        else:
            query = query.order_by(desc(Booking.created_at))
        
        bookings = query.all()
        
        return {
            "bookings": bookings,
            "total": total_count,
            "page": filters.page if filters else 1,
            "size": filters.size if filters else len(bookings),
            "total_pages": (total_count + (filters.size if filters else len(bookings)) - 1) // (filters.size if filters else len(bookings)) if total_count > 0 else 0
        }
    
    def get_all_bookings(self, filters: Optional[BookingFilterParams] = None) -> Dict[str, Any]:
        """Get all bookings with filtering and pagination (admin only)"""
        
        query = self.db.query(Booking).options(
            joinedload(Booking.test),
            joinedload(Booking.user)
        )
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and sorting
        if filters:
            offset = (filters.page - 1) * filters.size
            query = query.order_by(desc(Booking.created_at)).offset(offset).limit(filters.size)
        else:
            query = query.order_by(desc(Booking.created_at))
        
        bookings = query.all()
        
        return {
            "bookings": bookings,
            "total": total_count,
            "page": filters.page if filters else 1,
            "size": filters.size if filters else len(bookings),
            "total_pages": (total_count + (filters.size if filters else len(bookings)) - 1) // (filters.size if filters else len(bookings)) if total_count > 0 else 0
        }
    
    def update_booking_status(
        self, 
        booking_id: int, 
        status_update: BookingStatusUpdate,
        user_id: Optional[int] = None
    ) -> Booking:
        """Update booking status"""
        
        booking = self.get_booking_by_id(booking_id, user_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        # Validate status transition
        self._validate_status_transition(booking.status, status_update.status)
        
        # Update status
        booking.status = status_update.status
        if status_update.admin_notes:
            booking.admin_notes = status_update.admin_notes
        
        # Set timestamps based on status
        if status_update.status == BookingStatus.CANCELLED:
            booking.cancelled_at = datetime.now(timezone.utc)
        elif status_update.status == BookingStatus.COMPLETED:
            booking.completed_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(booking)
        
        return booking
    
    def cancel_booking(
        self, 
        booking_id: int, 
        cancellation_reason: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Booking:
        """Cancel a booking"""
        
        booking = self.get_booking_by_id(booking_id, user_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        if not booking.is_cancellable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Booking cannot be cancelled"
            )
        
        booking.status = BookingStatus.CANCELLED
        booking.cancellation_reason = cancellation_reason
        booking.cancelled_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(booking)
        
        return booking
    
    def admin_update_booking(self, booking_id: int, update_data: BookingAdminUpdate) -> Booking:
        """Admin update booking (full permissions)"""
        
        booking = self.get_booking_by_id(booking_id)
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        # Update fields
        if update_data.status:
            self._validate_status_transition(booking.status, update_data.status)
            booking.status = update_data.status
            
            # Set timestamps based on status
            if update_data.status == BookingStatus.CANCELLED:
                booking.cancelled_at = datetime.now(timezone.utc)
            elif update_data.status == BookingStatus.COMPLETED:
                booking.completed_at = datetime.now(timezone.utc)
        
        if update_data.admin_notes is not None:
            booking.admin_notes = update_data.admin_notes
        
        if update_data.appointment_date:
            booking.appointment_date = update_data.appointment_date
        
        self.db.commit()
        self.db.refresh(booking)
        
        return booking
    
    def get_booking_stats(self) -> BookingStatsResponse:
        """Get booking statistics"""
        
        total_bookings = self.db.query(Booking).count()
        
        # Status counts
        status_counts = self.db.query(
            Booking.status,
            func.count(Booking.id).label('count')
        ).group_by(Booking.status).all()
        
        status_dict = {status.value: 0 for status in BookingStatus}
        for status, count in status_counts:
            status_dict[status.value] = count
        
        # Today's bookings
        today = datetime.now(timezone.utc).date()
        today_bookings = self.db.query(Booking).filter(
            func.date(Booking.appointment_date) == today
        ).count()
        
        # Upcoming bookings
        upcoming_bookings = self.db.query(Booking).filter(
            Booking.appointment_date > datetime.now(timezone.utc),
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])
        ).count()
        
        # Home collection bookings
        home_collection_bookings = self.db.query(Booking).filter(
            Booking.home_collection == True
        ).count()
        
        return BookingStatsResponse(
            total_bookings=total_bookings,
            pending_bookings=status_dict.get('pending', 0),
            confirmed_bookings=status_dict.get('confirmed', 0),
            completed_bookings=status_dict.get('completed', 0),
            cancelled_bookings=status_dict.get('cancelled', 0),
            no_show_bookings=status_dict.get('no_show', 0),
            today_bookings=today_bookings,
            upcoming_bookings=upcoming_bookings,
            home_collection_bookings=home_collection_bookings
        )
    
    def get_upcoming_bookings(self, days: int = 7) -> List[Booking]:
        """Get upcoming bookings within specified days"""
        
        end_date = datetime.now(timezone.utc) + timedelta(days=days)
        
        return self.db.query(Booking).options(
            joinedload(Booking.test),
            joinedload(Booking.user)
        ).filter(
            Booking.appointment_date >= datetime.now(timezone.utc),
            Booking.appointment_date <= end_date,
            Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED])
        ).order_by(asc(Booking.appointment_date)).all()
    
    def _apply_filters(self, query, filters: BookingFilterParams):
        """Apply filters to booking query"""
        
        if filters.status:
            query = query.filter(Booking.status == filters.status)
        
        if filters.user_id:
            query = query.filter(Booking.user_id == filters.user_id)
        
        if filters.test_id:
            query = query.filter(Booking.test_id == filters.test_id)
        
        if filters.date_from:
            query = query.filter(Booking.appointment_date >= filters.date_from)
        
        if filters.date_to:
            query = query.filter(Booking.appointment_date <= filters.date_to)
        
        if filters.home_collection is not None:
            query = query.filter(Booking.home_collection == filters.home_collection)
        
        return query
    
    def _validate_status_transition(self, current_status: BookingStatus, new_status: BookingStatus):
        """Validate if status transition is allowed"""
        
        valid_transitions = {
            BookingStatus.PENDING: [BookingStatus.CONFIRMED, BookingStatus.CANCELLED],
            BookingStatus.CONFIRMED: [BookingStatus.COMPLETED, BookingStatus.CANCELLED, BookingStatus.NO_SHOW],
            BookingStatus.CANCELLED: [],  # Cannot change from cancelled
            BookingStatus.COMPLETED: [],  # Cannot change from completed
            BookingStatus.NO_SHOW: []     # Cannot change from no_show
        }
        
        if new_status not in valid_transitions.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot transition from {current_status.value} to {new_status.value}"
            )