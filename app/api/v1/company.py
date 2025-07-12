from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc
from datetime import datetime, timedelta
from app.database import get_db
from app.core.deps import get_current_active_user, get_admin_user, get_optional_user
from app.models.user import User
from app.models.company import Company, ContactMessage, MessageStatus
from app.schemas.company import (
    CompanyInfoResponse, CompanyInfoUpdate, ContactInfoResponse,
    ServicesListResponse, ContactFormSubmission, ContactFormResponse,
    ContactMessageResponse, ContactMessageUpdate, ContactMessageListResponse,
    ContactMessageFilter, ContactStats, CompanyProfileResponse,
    InquiryType, MessageStatus as MessageStatusEnum, Priority
)

router = APIRouter()


@router.get("/info", response_model=CompanyInfoResponse)
async def get_company_info(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get company information.
    Public endpoint - no authentication required.
    """
    company = db.query(Company).filter(Company.is_active == True).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company information not found"
        )
    
    return company


@router.put("/info", response_model=CompanyInfoResponse)
async def update_company_info(
    company_data: CompanyInfoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Update company information.
    Requires admin permissions.
    """
    company = db.query(Company).filter(Company.is_active == True).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company information not found"
        )
    
    # Update only provided fields
    update_data = company_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)
    
    db.commit()
    db.refresh(company)
    
    return company


@router.get("/contact", response_model=ContactInfoResponse)
async def get_contact_info(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get company contact information.
    Public endpoint - no authentication required.
    """
    company = db.query(Company).filter(Company.is_active == True).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company contact information not found"
        )
    
    # Enhance with computed properties
    company.full_address = company.full_address
    
    return company


@router.get("/services", response_model=ServicesListResponse)
async def get_services(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get list of services offered by the company.
    Public endpoint - no authentication required.
    """
    company = db.query(Company).filter(Company.is_active == True).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company information not found"
        )
    
    services = company.get_service_list()
    specializations = company.specializations if company.specializations else []
    certifications = company.certifications if company.certifications else []
    
    return ServicesListResponse(
        services=services,
        specializations=specializations,
        certifications=certifications,
        total_services=len(services)
    )


@router.post("/contact", response_model=ContactFormResponse, status_code=status.HTTP_201_CREATED)
async def submit_contact_form(
    contact_data: ContactFormSubmission,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit a contact form message.
    Public endpoint - no authentication required.
    """
    # Get company info for response
    company = db.query(Company).filter(Company.is_active == True).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable"
        )
    
    # Create contact message
    contact_message = ContactMessage(
        full_name=contact_data.full_name,
        email=contact_data.email,
        phone=contact_data.phone,
        subject=contact_data.subject,
        message=contact_data.message,
        inquiry_type=contact_data.inquiry_type.value,
        source=contact_data.source,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        # Set priority based on inquiry type
        priority="high" if contact_data.inquiry_type in [InquiryType.COMPLAINT, InquiryType.SUPPORT] else "normal"
    )
    
    db.add(contact_message)
    db.commit()
    db.refresh(contact_message)
    
    # Determine estimated response time
    if contact_message.priority in ["urgent", "high"]:
        estimated_response = "4-6 hours"
    else:
        estimated_response = "24-48 hours"
    
    return ContactFormResponse(
        message="Thank you for contacting us. We have received your message and will respond soon.",
        contact_id=contact_message.id,
        estimated_response_time=estimated_response,
        support_email=company.email or "support@vitachecklabs.com",
        support_phone=company.phone_primary
    )


@router.get("/profile", response_model=CompanyProfileResponse)
async def get_company_profile(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get complete company profile including info, contact, and services.
    Public endpoint - no authentication required.
    """
    company = db.query(Company).filter(Company.is_active == True).first()
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company profile not found"
        )
    
    # Prepare services data
    services = company.get_service_list()
    specializations = company.specializations if company.specializations else []
    certifications = company.certifications if company.certifications else []
    
    services_response = ServicesListResponse(
        services=services,
        specializations=specializations,
        certifications=certifications,
        total_services=len(services)
    )
    
    # Prepare settings data
    from app.schemas.company import CompanySettings, BusinessHours
    
    business_hours = None
    if company.operating_hours:
        business_hours = BusinessHours(**company.operating_hours)
    
    settings = CompanySettings(
        accepts_home_collection=company.accepts_home_collection,
        home_collection_radius_km=company.home_collection_radius_km or 25,
        minimum_order_amount=company.minimum_order_amount,
        is_24x7=company.is_24x7,
        emergency_contact=company.emergency_contact,
        operating_hours=business_hours
    )
    
    # Enhance contact info with computed properties
    company.full_address = company.full_address
    
    return CompanyProfileResponse(
        info=company,
        contact=company,
        services=services_response,
        settings=settings
    )


# Admin endpoints for managing contact messages
@router.get("/contact/messages", response_model=ContactMessageListResponse)
async def get_contact_messages(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[MessageStatusEnum] = Query(None, description="Filter by status"),
    inquiry_type: Optional[InquiryType] = Query(None, description="Filter by inquiry type"),
    priority: Optional[Priority] = Query(None, description="Filter by priority"),
    responded: Optional[bool] = Query(None, description="Filter by response status"),
    date_from: Optional[datetime] = Query(None, description="Filter messages from date"),
    date_to: Optional[datetime] = Query(None, description="Filter messages to date"),
    search: Optional[str] = Query(None, min_length=1, description="Search in name, email, subject, message"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Get list of contact messages with filtering and pagination.
    Requires admin permissions.
    """
    # Build query
    query = db.query(ContactMessage)
    
    # Apply filters
    if status:
        query = query.filter(ContactMessage.status == status.value)
    
    if inquiry_type:
        query = query.filter(ContactMessage.inquiry_type == inquiry_type.value)
    
    if priority:
        query = query.filter(ContactMessage.priority == priority.value)
    
    if responded is not None:
        if responded:
            query = query.filter(ContactMessage.responded_at.isnot(None))
        else:
            query = query.filter(ContactMessage.responded_at.is_(None))
    
    if date_from:
        query = query.filter(ContactMessage.created_at >= date_from)
    
    if date_to:
        query = query.filter(ContactMessage.created_at <= date_to)
    
    if search:
        search_filter = or_(
            ContactMessage.full_name.ilike(f"%{search}%"),
            ContactMessage.email.ilike(f"%{search}%"),
            ContactMessage.subject.ilike(f"%{search}%"),
            ContactMessage.message.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Get total count
    total = query.count()
    
    # Apply sorting and pagination
    offset = (page - 1) * per_page
    messages = (
        query
        .order_by(desc(ContactMessage.created_at))
        .offset(offset)
        .limit(per_page)
        .all()
    )
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    # Enhance messages with computed properties
    for message in messages:
        message.is_urgent = message.is_urgent
        message.response_time_hours = message.response_time_hours
    
    return ContactMessageListResponse(
        messages=messages,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/contact/messages/{message_id}", response_model=ContactMessageResponse)
async def get_contact_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Get a specific contact message by ID.
    Requires admin permissions.
    """
    message = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact message not found"
        )
    
    # Mark as read if it's new
    if message.status == MessageStatus.NEW:
        message.mark_as_read()
        db.commit()
        db.refresh(message)
    
    # Enhance with computed properties
    message.is_urgent = message.is_urgent
    message.response_time_hours = message.response_time_hours
    
    return message


@router.put("/contact/messages/{message_id}", response_model=ContactMessageResponse)
async def update_contact_message(
    message_id: int,
    message_data: ContactMessageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Update a contact message (respond, change status, etc.).
    Requires admin permissions.
    """
    message = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact message not found"
        )
    
    # Update only provided fields
    update_data = message_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value:
            setattr(message, field, value.value)
        elif field == "priority" and value:
            setattr(message, field, value.value)
        else:
            setattr(message, field, value)
    
    # Set responded_at if response_message is provided and not already set
    if message_data.response_message and not message.responded_at:
        message.responded_at = func.now()
        if not message.responded_by:
            message.responded_by = current_user.full_name or current_user.email
    
    db.commit()
    db.refresh(message)
    
    # Enhance with computed properties
    message.is_urgent = message.is_urgent
    message.response_time_hours = message.response_time_hours
    
    return message


@router.delete("/contact/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Delete a contact message.
    Requires admin permissions.
    """
    message = db.query(ContactMessage).filter(ContactMessage.id == message_id).first()
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact message not found"
        )
    
    db.delete(message)
    db.commit()


@router.get("/contact/stats", response_model=ContactStats)
async def get_contact_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Get contact messages statistics.
    Requires admin permissions.
    """
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Get basic counts
    total_messages = db.query(ContactMessage).count()
    new_messages = db.query(ContactMessage).filter(ContactMessage.status == MessageStatus.NEW).count()
    pending_response = db.query(ContactMessage).filter(
        ContactMessage.status.in_([MessageStatus.NEW, MessageStatus.READ, MessageStatus.IN_PROGRESS])
    ).count()
    resolved_messages = db.query(ContactMessage).filter(
        ContactMessage.status.in_([MessageStatus.RESOLVED, MessageStatus.CLOSED])
    ).count()
    urgent_messages = db.query(ContactMessage).filter(
        ContactMessage.priority.in_(["urgent", "high"])
    ).count()
    
    # Time-based counts
    messages_this_week = db.query(ContactMessage).filter(
        ContactMessage.created_at >= week_ago
    ).count()
    messages_this_month = db.query(ContactMessage).filter(
        ContactMessage.created_at >= month_ago
    ).count()
    
    # Calculate average response time
    responded_messages = db.query(ContactMessage).filter(
        ContactMessage.responded_at.isnot(None),
        ContactMessage.created_at.isnot(None)
    ).all()
    
    total_response_hours = 0
    if responded_messages:
        response_times = []
        for msg in responded_messages:
            response_time = msg.response_time_hours
            if response_time:
                response_times.append(response_time)
        
        if response_times:
            total_response_hours = sum(response_times) / len(response_times)
    
    return ContactStats(
        total_messages=total_messages,
        new_messages=new_messages,
        pending_response=pending_response,
        resolved_messages=resolved_messages,
        average_response_time_hours=total_response_hours,
        urgent_messages=urgent_messages,
        messages_this_week=messages_this_week,
        messages_this_month=messages_this_month
    )