from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc
from datetime import datetime, timedelta
import uuid
import os
import mimetypes
from app.database import get_db
from app.core.deps import get_current_active_user, get_admin_user
from app.models.user import User
from app.models.report import Report, ReportStatus
from app.models.lab_test import LabTest
from app.schemas.report import (
    ReportCreate, ReportUpdate, ReportResponse, ReportListResponse,
    ReportFilter, ReportStats, ReportShare, ReportFileUpload, ReportDownload,
    ReportStatus as ReportStatusEnum, PaymentStatus, Priority
)
from app.services.s3_service import S3Service

router = APIRouter()


@router.get("/", response_model=ReportListResponse)
async def get_reports(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[ReportStatusEnum] = Query(None, description="Filter by status"),
    lab_test_id: Optional[int] = Query(None, description="Filter by lab test"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
    priority: Optional[Priority] = Query(None, description="Filter by priority"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    date_from: Optional[datetime] = Query(None, description="Filter reports from date"),
    date_to: Optional[datetime] = Query(None, description="Filter reports to date"),
    search: Optional[str] = Query(None, min_length=1, description="Search in report number, notes"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get list of user's reports with filtering and pagination.
    Users can only see their own reports unless they are admin.
    """
    # Build base query
    query = db.query(Report).join(LabTest).join(User)
    
    # Apply user filter - users can only see their own reports unless admin
    if not current_user.is_admin():
        query = query.filter(Report.user_id == current_user.id)
    
    # Apply filters
    if status:
        query = query.filter(Report.status == status.value)
    
    if lab_test_id:
        query = query.filter(Report.lab_test_id == lab_test_id)
    
    if payment_status:
        query = query.filter(Report.payment_status == payment_status.value)
    
    if priority:
        query = query.filter(Report.priority == priority.value)
    
    if is_verified is not None:
        query = query.filter(Report.is_verified == is_verified)
    
    if date_from:
        query = query.filter(Report.created_at >= date_from)
    
    if date_to:
        query = query.filter(Report.created_at <= date_to)
    
    if search:
        search_filter = or_(
            Report.report_number.ilike(f"%{search}%"),
            Report.notes.ilike(f"%{search}%"),
            LabTest.name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    # Get total count
    total = query.count()
    
    # Apply sorting and pagination
    offset = (page - 1) * per_page
    reports = (
        query
        .order_by(desc(Report.created_at))
        .offset(offset)
        .limit(per_page)
        .all()
    )
    
    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page
    
    # Enhance reports with computed properties
    for report in reports:
        report.amount_in_rupees = report.amount_in_rupees
        report.can_be_downloaded = report.can_be_downloaded()
        turnaround = report.get_turnaround_time()
        report.turnaround_time_hours = turnaround.total_seconds() / 3600 if turnaround else None
    
    return ReportListResponse(
        reports=reports,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific report by ID.
    Users can only access their own reports unless they are admin.
    """
    query = db.query(Report).join(LabTest).join(User)
    
    # Apply user filter - users can only see their own reports unless admin
    if not current_user.is_admin():
        query = query.filter(Report.user_id == current_user.id)
    
    report = query.filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Enhance report with computed properties
    report.amount_in_rupees = report.amount_in_rupees
    report.can_be_downloaded = report.can_be_downloaded()
    turnaround = report.get_turnaround_time()
    report.turnaround_time_hours = turnaround.total_seconds() / 3600 if turnaround else None
    
    return report


@router.post("/", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    report_data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new report.
    Requires authentication.
    """
    # Verify lab test exists and is active
    lab_test = db.query(LabTest).filter(
        LabTest.id == report_data.lab_test_id,
        LabTest.is_active == True
    ).first()
    
    if not lab_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab test not found or inactive"
        )
    
    # Generate unique report number
    report_number = f"RPT{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:8].upper()}"
    
    # Create new report
    report = Report(
        user_id=current_user.id,
        lab_test_id=report_data.lab_test_id,
        report_number=report_number,
        scheduled_at=report_data.scheduled_at,
        collection_location=report_data.collection_location,
        collection_notes=report_data.collection_notes,
        priority=report_data.priority.value,
        notes=report_data.notes,
        amount_charged=int(lab_test.price * 100) if lab_test.price else None  # Convert to paisa
    )
    
    db.add(report)
    db.commit()
    db.refresh(report)
    
    # Enhance report with computed properties
    report.amount_in_rupees = report.amount_in_rupees
    report.can_be_downloaded = report.can_be_downloaded()
    
    return report


@router.put("/{report_id}", response_model=ReportResponse)
async def update_report(
    report_id: int,
    report_data: ReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a report.
    Users can only update their own reports unless they are admin.
    Admin can update any report.
    """
    query = db.query(Report)
    
    # Apply user filter - users can only update their own reports unless admin
    if not current_user.is_admin():
        query = query.filter(Report.user_id == current_user.id)
    
    report = query.filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Update only provided fields
    update_data = report_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status" and value:
            # Use the model's update_status method for proper timestamp handling
            report.update_status(ReportStatus(value))
        else:
            setattr(report, field, value)
    
    db.commit()
    db.refresh(report)
    
    # Enhance report with computed properties
    report.amount_in_rupees = report.amount_in_rupees
    report.can_be_downloaded = report.can_be_downloaded()
    turnaround = report.get_turnaround_time()
    report.turnaround_time_hours = turnaround.total_seconds() / 3600 if turnaround else None
    
    return report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a report.
    Users can only delete their own reports unless they are admin.
    Admin can delete any report.
    """
    query = db.query(Report)
    
    # Apply user filter - users can only delete their own reports unless admin
    if not current_user.is_admin():
        query = query.filter(Report.user_id == current_user.id)
    
    report = query.filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Check if report can be deleted (business rule: only pending reports can be deleted)
    if report.status not in [ReportStatus.PENDING, ReportStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending or cancelled reports can be deleted"
        )
    
    # Delete associated file from S3 if exists
    if report.file_path:
        try:
            s3_service = S3Service()
            s3_service.delete_file(report.file_path)
        except Exception as e:
            # Log error but don't fail the delete operation
            print(f"Warning: Failed to delete file from S3: {e}")
    
    db.delete(report)
    db.commit()


@router.post("/{report_id}/upload", response_model=ReportResponse)
async def upload_report_file(
    report_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a file for a report.
    Only admin users can upload files.
    Supports PDF and image files.
    """
    if not current_user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can upload report files"
        )
    
    report = db.query(Report).filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    # Validate file type
    allowed_types = {
        'application/pdf': '.pdf',
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif'
    }
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not supported. Allowed types: PDF, JPEG, PNG, GIF"
        )
    
    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 10MB limit"
        )
    
    try:
        # Upload to S3
        s3_service = S3Service()
        file_extension = allowed_types[file.content_type]
        s3_key = f"reports/{report.report_number}/{uuid.uuid4().hex}{file_extension}"
        
        # Reset file pointer and upload
        await file.seek(0)
        s3_service.upload_file(file_content, s3_key, file.content_type)
        
        # Delete old file if exists
        if report.file_path:
            try:
                s3_service.delete_file(report.file_path)
            except Exception as e:
                print(f"Warning: Failed to delete old file from S3: {e}")
        
        # Update report with file information
        report.file_path = s3_key
        report.file_original_name = file.filename
        report.file_size = len(file_content)
        report.file_type = file.content_type
        
        # Update status to completed if it was pending
        if report.status == ReportStatus.PENDING:
            report.update_status(ReportStatus.COMPLETED)
        
        db.commit()
        db.refresh(report)
        
        # Enhance report with computed properties
        report.amount_in_rupees = report.amount_in_rupees
        report.can_be_downloaded = report.can_be_downloaded()
        
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.get("/{report_id}/download", response_model=ReportDownload)
async def get_report_download_url(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a presigned download URL for a report file.
    Users can only download their own reports unless they are admin.
    """
    query = db.query(Report)
    
    # Apply user filter - users can only download their own reports unless admin
    if not current_user.is_admin():
        query = query.filter(Report.user_id == current_user.id)
    
    report = query.filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    if not report.can_be_downloaded():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report file is not available for download"
        )
    
    try:
        # Generate presigned URL
        s3_service = S3Service()
        download_url = s3_service.generate_presigned_url(
            report.file_path,
            expiration=3600  # 1 hour
        )
        
        return ReportDownload(
            download_url=download_url,
            expires_at=datetime.now() + timedelta(hours=1),
            file_name=report.file_original_name or f"report_{report.report_number}.pdf",
            file_size=report.file_size or 0
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}"
        )


@router.post("/{report_id}/share", response_model=ReportResponse)
async def share_report(
    report_id: int,
    share_data: ReportShare,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Share a report with specified email addresses.
    Users can only share their own reports unless they are admin.
    """
    query = db.query(Report)
    
    # Apply user filter - users can only share their own reports unless admin
    if not current_user.is_admin():
        query = query.filter(Report.user_id == current_user.id)
    
    report = query.filter(Report.id == report_id).first()
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    
    if not report.can_be_downloaded():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report is not ready for sharing"
        )
    
    # Update report sharing information
    import json
    report.is_shared = True
    report.shared_at = func.now()
    report.shared_with = json.dumps(share_data.shared_with)
    
    # In a real implementation, you would send emails here
    # For now, we'll just update the database
    
    db.commit()
    db.refresh(report)
    
    # Enhance report with computed properties
    report.amount_in_rupees = report.amount_in_rupees
    report.can_be_downloaded = report.can_be_downloaded()
    
    return report


@router.get("/stats/overview", response_model=ReportStats)
async def get_report_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get report statistics.
    Users see stats for their own reports, admins see global stats.
    """
    # Build base query
    query = db.query(Report)
    
    # Apply user filter - users can only see their own stats unless admin
    if not current_user.is_admin():
        query = query.filter(Report.user_id == current_user.id)
    
    # Get basic counts
    total_reports = query.count()
    pending_reports = query.filter(Report.status == ReportStatus.PENDING).count()
    completed_reports = query.filter(Report.status.in_([
        ReportStatus.COMPLETED, ReportStatus.REVIEWED, ReportStatus.DELIVERED
    ])).count()
    paid_reports = query.filter(Report.payment_status == "paid").count()
    unpaid_reports = query.filter(Report.payment_status == "pending").count()
    verified_reports = query.filter(Report.is_verified == True).count()
    
    # Calculate average turnaround time
    completed_query = query.filter(
        Report.collected_at.isnot(None),
        Report.delivered_at.isnot(None)
    )
    
    avg_turnaround_hours = 0
    if completed_query.count() > 0:
        turnaround_times = []
        for report in completed_query.all():
            turnaround = report.get_turnaround_time()
            if turnaround:
                turnaround_times.append(turnaround.total_seconds() / 3600)
        
        if turnaround_times:
            avg_turnaround_hours = sum(turnaround_times) / len(turnaround_times)
    
    # Calculate total revenue (from paid reports)
    revenue_result = query.filter(
        Report.payment_status == "paid",
        Report.amount_charged.isnot(None)
    ).with_entities(func.sum(Report.amount_charged)).scalar()
    
    total_revenue = (revenue_result or 0) / 100  # Convert from paisa to rupees
    
    return ReportStats(
        total_reports=total_reports,
        pending_reports=pending_reports,
        completed_reports=completed_reports,
        average_turnaround_hours=avg_turnaround_hours,
        total_revenue=total_revenue,
        paid_reports=paid_reports,
        unpaid_reports=unpaid_reports,
        verified_reports=verified_reports
    )