"""
Enhanced Reports API with S3 integration for DynamoDB + S3 architecture
This replaces the SQLAlchemy-based reports API with DynamoDB + S3
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, RedirectResponse
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
import uuid
import mimetypes
import io
import json

from app.core.deps_dynamodb import get_current_active_user, get_admin_user
from app.services.s3_reports_service import s3_reports_service
from app.schemas.report import (
    ReportCreate, ReportUpdate, ReportResponse,
    ReportStatus as ReportStatusEnum, PaymentStatus, Priority
)

router = APIRouter()

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
reports_table = dynamodb.Table('vitachecklabs-reports')

@router.post("/upload", response_model=Dict[str, Any])
async def upload_report_file(
    report_id: str = Form(..., description="Report ID"),
    file: UploadFile = File(..., description="Report file (PDF, JPG, PNG)"),
    current_user: dict = Depends(get_admin_user)
):
    """
    Upload a lab report file to S3 and update DynamoDB metadata
    """
    # Validate file type
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not allowed. Use PDF, JPG, or PNG."
        )
    
    # Validate file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 10MB limit"
        )
    
    try:
        # Check if report exists and belongs to user
        response = reports_table.get_item(Key={'report_id': report_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report = response['Item']
        # Admin can upload to any report
        
        # Upload to S3
        file_obj = io.BytesIO(file_content)
        upload_result = s3_reports_service.upload_report(
            file_content=file_obj,
            filename=file.filename,
            user_id=current_user['user_id'],
            report_id=report_id,
            content_type=file.content_type
        )
        
        if not upload_result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {upload_result['error']}"
            )
        
        # Update DynamoDB with file metadata
        reports_table.update_item(
            Key={'report_id': report_id},
            UpdateExpression="""
                SET s3_file_key = :s3_key,
                    file_original_name = :filename,
                    file_size = :file_size,
                    file_type = :content_type,
                    updated_at = :updated_at,
                    #status = :status
            """,
            ExpressionAttributeNames={
                '#status': 'status'
            },
            ExpressionAttributeValues={
                ':s3_key': upload_result['s3_key'],
                ':filename': file.filename,
                ':file_size': upload_result['file_size'],
                ':content_type': file.content_type,
                ':updated_at': datetime.utcnow().isoformat() + 'Z',
                ':status': 'completed'
            }
        )
        
        return {
            "success": True,
            "message": "File uploaded successfully",
            "report_id": report_id,
            "s3_key": upload_result['s3_key'],
            "file_size": upload_result['file_size'],
            "filename": file.filename
        }
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )

@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Download a report file from S3 using presigned URL
    """
    try:
        # Get report from DynamoDB
        response = reports_table.get_item(Key={'report_id': report_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report = response['Item']
        if report['user_id'] != current_user['user_id'] and current_user.get('role') != 'ADMIN':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to download this report"
            )
        
        if not report.get('s3_file_key'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report file not found"
            )
        
        # Generate presigned URL for download
        download_url = s3_reports_service.generate_presigned_url(
            s3_key=report['s3_file_key'],
            operation='get_object',
            expiration=3600  # 1 hour
        )
        
        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate download URL"
            )
        
        # Return the URL in JSON format instead of redirect to avoid CORS issues
        return {
            "success": True,
            "download_url": download_url,
            "filename": report.get('file_original_name', f"report_{report_id}"),
            "file_size": report.get('file_size'),
            "content_type": report.get('file_type'),
            "expires_in": 3600
        }
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.get("/{report_id}/download-direct")
async def download_report_direct(
    report_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Download a report file directly from S3 (streams content)
    """
    try:
        # Get report from DynamoDB
        response = reports_table.get_item(Key={'report_id': report_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report = response['Item']
        if report['user_id'] != current_user['user_id'] and current_user.get('role') != 'ADMIN':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to download this report"
            )
        
        if not report.get('s3_file_key'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report file not found"
            )
        
        # Download file content from S3
        file_content = s3_reports_service.download_report(report['s3_file_key'])
        if file_content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage"
            )
        
        # Determine content type and filename
        content_type = report.get('file_type', 'application/octet-stream')
        filename = report.get('file_original_name', f"report_{report_id}")
        
        # Create streaming response
        import io
        
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Content-Length": str(len(file_content)),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Methods": "GET"
            }
        )
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {str(e)}"
        )

@router.get("/", response_model=List[Dict[str, Any]])
async def get_user_reports(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get user's reports from DynamoDB
    """
    try:
        # Use GSI to query user's reports
        scan_params = {
            'IndexName': 'user-status-index',
            'KeyConditionExpression': boto3.dynamodb.conditions.Key('user_id').eq(current_user['user_id'])
        }
        
        if status:
            scan_params['FilterExpression'] = boto3.dynamodb.conditions.Attr('status').eq(status)
        
        response = reports_table.query(**scan_params)
        
        reports = response.get('Items', [])
        
        # Sort by created_at (most recent first)
        reports.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_reports = reports[start_idx:end_idx]
        
        # Add download URLs for reports with files
        for report in paginated_reports:
            if report.get('s3_file_key'):
                report['download_url'] = f"/api/v1/reports/{report['report_id']}/download"
                report['has_file'] = True
            else:
                report['has_file'] = False
        
        return paginated_reports
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.post("/", response_model=Dict[str, Any])
async def create_report(
    user_id: str = Form(..., description="User ID for whom the report is being created"),
    lab_test_id: str = Form(..., description="Lab test ID"),
    patient_notes: Optional[str] = Form(None, description="Patient notes"),
    scheduled_at: Optional[datetime] = Form(None, description="Scheduled date"),
    current_user: dict = Depends(get_admin_user)
):
    """
    Create a new report in DynamoDB (Admin only)
    """
    try:
        # Validate that the user exists (check DynamoDB users table)
        users_table = dynamodb.Table('vitachecklabs-users')
        user_response = users_table.get_item(Key={'user_id': user_id})
        if 'Item' not in user_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Validate that the lab test exists
        lab_tests_table = dynamodb.Table('vitachecklabs-lab-tests')
        test_response = lab_tests_table.get_item(Key={'test_id': lab_test_id})
        if 'Item' not in test_response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lab test with ID {lab_test_id} not found"
            )
        
        report_id = f"rpt_{uuid.uuid4()}"
        report_number = f"RPT{datetime.utcnow().strftime('%Y%m%d')}{report_id[-6:]}"
        
        report_item = {
            'report_id': report_id,
            'user_id': user_id,  # Use the provided user_id
            'lab_test_id': lab_test_id,
            'report_number': report_number,
            'status': 'pending',
            'scheduled_at': scheduled_at.isoformat() + 'Z' if scheduled_at else '',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'updated_at': datetime.utcnow().isoformat() + 'Z',
            'notes': patient_notes or '',
            'priority': 'normal',
            'payment_status': 'pending',
            'is_verified': False
        }
        
        reports_table.put_item(Item=report_item)
        
        return {
            "success": True,
            "message": "Report created successfully",
            "report_id": report_id,
            "report_number": report_number,
            "user_id": user_id,
            "lab_test_id": lab_test_id,
            "status": "pending"
        }
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.get("/{report_id}", response_model=Dict[str, Any])
async def get_report_details(
    report_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get detailed report information
    """
    try:
        response = reports_table.get_item(Key={'report_id': report_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report = response['Item']
        if report['user_id'] != current_user['user_id'] and current_user.get('role') != 'ADMIN':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this report"
            )
        
        # Add file information
        if report.get('s3_file_key'):
            report['download_url'] = f"/api/v1/reports/{report_id}/download"
            report['has_file'] = True
            
            # Get file metadata from S3
            file_metadata = s3_reports_service.get_file_metadata(report['s3_file_key'])
            if file_metadata:
                report['file_metadata'] = file_metadata
        else:
            report['has_file'] = False
        
        return report
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete a report and its associated file
    """
    try:
        # Get report first
        response = reports_table.get_item(Key={'report_id': report_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found"
            )
        
        report = response['Item']
        if report['user_id'] != current_user['user_id'] and current_user.get('role') != 'ADMIN':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this report"
            )
        
        # Delete file from S3 if exists
        if report.get('s3_file_key'):
            s3_reports_service.delete_report(report['s3_file_key'])
        
        # Delete from DynamoDB
        reports_table.delete_item(Key={'report_id': report_id})
        
        return {"success": True, "message": "Report deleted successfully"}
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )