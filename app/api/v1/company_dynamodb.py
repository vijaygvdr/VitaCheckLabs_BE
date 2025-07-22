"""
Company API endpoints using DynamoDB
Replaces SQLAlchemy-based company API with DynamoDB version
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
import uuid
import json
from decimal import Decimal

from app.core.deps_dynamodb import get_current_active_user, get_admin_user
from app.core.config import settings
from app.schemas.company import (
    CompanyInfoResponse, CompanyInfoUpdate, ContactInfoResponse,
    ServicesListResponse, ContactFormSubmission, ContactFormResponse,
    ContactMessageResponse, ContactMessageUpdate, ContactMessageListResponse,
    ContactMessageFilter, ContactStats, CompanyProfileResponse,
    InquiryType, MessageStatus as MessageStatusEnum, Priority
)

router = APIRouter()

# DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=settings.AWS_REGION)
company_table = dynamodb.Table('vitachecklabs-company')
contact_messages_table = dynamodb.Table('vitachecklabs-contact-messages')


@router.get("/info", response_model=Dict[str, Any])
async def get_company_info():
    """
    Get company information.
    Public endpoint - no authentication required.
    """
    try:
        response = company_table.get_item(Key={'id': 'company-info'})
        
        if 'Item' not in response:
            # Return default company info if none exists
            return {
                "id": "company-info",
                "name": "VitaCheckLabs",
                "legal_name": "VitaCheckLabs Private Limited",
                "description": "Premier diagnostic laboratory providing comprehensive health testing services",
                "mission_statement": "To provide accurate, reliable, and timely diagnostic services to improve healthcare outcomes",
                "vision_statement": "To be the leading diagnostic laboratory known for excellence and innovation",
                "tagline": "Your Health, Our Priority",
                "established_year": 2020,
                "license_number": "LAB-2020-001",
                "accreditation": "NABL Accredited",
                "logo_url": "/static/logo.png",
                "website": "https://vitachecklabs.com",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
        
        # Convert DynamoDB Decimal to float/int for JSON serialization
        item = json.loads(json.dumps(response['Item'], default=str))
        return item
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.put("/info", response_model=Dict[str, Any])
async def update_company_info(
    company_data: CompanyInfoUpdate,
    current_user: dict = Depends(get_admin_user)
):
    """
    Update company information.
    Requires admin permissions.
    """
    try:
        # Prepare update data
        update_data = company_data.dict(exclude_unset=True)
        update_data['updated_at'] = datetime.now().isoformat()
        update_data['updated_by'] = current_user.get('username', 'admin')
        
        # Build update expression
        update_expression = "SET "
        expression_values = {}
        
        for key, value in update_data.items():
            update_expression += f"#{key} = :{key}, "
            expression_values[f":{key}"] = value
        
        update_expression = update_expression.rstrip(", ")
        
        # Create attribute names mapping to handle reserved keywords
        expression_names = {f"#{key}": key for key in update_data.keys()}
        
        response = company_table.update_item(
            Key={'id': 'company-info'},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW"
        )
        
        # Convert DynamoDB Decimal to float/int for JSON serialization
        item = json.loads(json.dumps(response['Attributes'], default=str))
        return item
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/contact", response_model=Dict[str, Any])
async def get_contact_info():
    """
    Get contact information.
    Public endpoint - no authentication required.
    """
    try:
        response = company_table.get_item(Key={'id': 'contact-info'})
        
        if 'Item' not in response:
            # Return default contact info
            return {
                "id": "contact-info",
                "email": "info@vitachecklabs.com",
                "phone": "+91-9999999999",
                "whatsapp": "+91-9999999999",
                "address": "123 Health Street, Medical District, City - 123456",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400001",
                "country": "India",
                "business_hours": {
                    "monday": "9:00 AM - 6:00 PM",
                    "tuesday": "9:00 AM - 6:00 PM",
                    "wednesday": "9:00 AM - 6:00 PM",
                    "thursday": "9:00 AM - 6:00 PM",
                    "friday": "9:00 AM - 6:00 PM",
                    "saturday": "9:00 AM - 4:00 PM",
                    "sunday": "Closed"
                },
                "emergency_contact": "+91-8888888888",
                "support_email": "support@vitachecklabs.com"
            }
        
        item = json.loads(json.dumps(response['Item'], default=str))
        return item
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/services", response_model=Dict[str, Any])
async def get_services():
    """
    Get services list.
    Public endpoint - no authentication required.
    """
    return {
        "services": [
            {
                "category": "Blood Tests",
                "description": "Comprehensive blood analysis and testing",
                "tests": ["Complete Blood Count", "Blood Sugar", "Cholesterol", "Thyroid Function"]
            },
            {
                "category": "Imaging",
                "description": "Advanced medical imaging services",
                "tests": ["X-Ray", "Ultrasound", "ECG", "Echo"]
            },
            {
                "category": "Specialized Tests",
                "description": "Specialized diagnostic tests",
                "tests": ["Allergy Tests", "Hormone Tests", "Vitamin Deficiency", "Cardiac Markers"]
            },
            {
                "category": "Home Collection",
                "description": "Sample collection at your doorstep",
                "tests": ["Blood Collection", "Urine Collection", "Swab Collection"]
            }
        ],
        "features": [
            "NABL Accredited Laboratory",
            "Home Sample Collection",
            "Online Report Delivery",
            "Expert Consultation",
            "24/7 Customer Support",
            "Advanced Equipment",
            "Quick Turnaround Time",
            "Affordable Pricing"
        ]
    }


@router.post("/contact", response_model=Dict[str, Any])
async def submit_contact_form(contact_form: ContactFormSubmission):
    """
    Submit contact form.
    Public endpoint - no authentication required.
    """
    try:
        # Generate unique message ID
        message_id = str(uuid.uuid4())
        
        # Prepare message data
        message_data = {
            'id': message_id,
            'name': contact_form.name,
            'email': contact_form.email,
            'phone': contact_form.phone,
            'inquiry_type': contact_form.inquiry_type,
            'subject': contact_form.subject,
            'message': contact_form.message,
            'status': MessageStatusEnum.NEW,
            'priority': Priority.NORMAL,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'ip_address': getattr(contact_form, 'ip_address', None),
            'user_agent': getattr(contact_form, 'user_agent', None)
        }
        
        # Save to DynamoDB
        contact_messages_table.put_item(Item=message_data)
        
        return {
            "message_id": message_id,
            "status": "submitted",
            "message": "Thank you for contacting us. We will get back to you soon.",
            "estimated_response_time": "24-48 hours"
        }
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/profile", response_model=Dict[str, Any])
async def get_company_profile():
    """
    Get complete company profile.
    Public endpoint - no authentication required.
    """
    try:
        # Get company info and contact info
        company_info = await get_company_info()
        contact_info = await get_contact_info()
        services = await get_services()
        
        return {
            "company": company_info,
            "contact": contact_info,
            "services": services,
            "certifications": [
                "NABL Accredited",
                "ISO 15189:2012 Certified",
                "CAP Accredited",
                "NABH Accredited"
            ],
            "achievements": [
                "Over 1 Million Tests Processed",
                "99.8% Accuracy Rate",
                "24/7 Service Availability",
                "Pan India Presence"
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving company profile: {str(e)}"
        )


# Admin endpoints for contact message management
@router.get("/contact/messages", response_model=Dict[str, Any])
async def get_contact_messages(
    status_filter: Optional[MessageStatusEnum] = Query(None),
    priority: Optional[Priority] = Query(None),
    inquiry_type: Optional[InquiryType] = Query(None),
    limit: int = Query(50, le=100),
    current_user: dict = Depends(get_admin_user)
):
    """
    Get contact messages with filtering.
    Requires admin permissions.
    """
    try:
        # Build scan parameters
        scan_kwargs = {
            'Limit': limit
        }
        
        # Add filters
        filter_expressions = []
        expression_values = {}
        
        if status_filter:
            filter_expressions.append("#status = :status")
            expression_values[":status"] = status_filter
            scan_kwargs['ExpressionAttributeNames'] = {"#status": "status"}
        
        if priority:
            filter_expressions.append("priority = :priority")
            expression_values[":priority"] = priority
            
        if inquiry_type:
            filter_expressions.append("inquiry_type = :inquiry_type")
            expression_values[":inquiry_type"] = inquiry_type
        
        if filter_expressions:
            scan_kwargs['FilterExpression'] = " AND ".join(filter_expressions)
            scan_kwargs['ExpressionAttributeValues'] = expression_values
        
        response = contact_messages_table.scan(**scan_kwargs)
        
        # Convert DynamoDB items
        messages = []
        for item in response.get('Items', []):
            message = json.loads(json.dumps(item, default=str))
            messages.append(message)
        
        # Sort by created_at descending
        messages.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return {
            "messages": messages,
            "total": len(messages),
            "has_more": 'LastEvaluatedKey' in response
        }
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/contact/messages/{message_id}", response_model=Dict[str, Any])
async def get_contact_message(
    message_id: str,
    current_user: dict = Depends(get_admin_user)
):
    """
    Get specific contact message.
    Requires admin permissions.
    """
    try:
        response = contact_messages_table.get_item(Key={'id': message_id})
        
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact message not found"
            )
        
        # Convert DynamoDB item
        message = json.loads(json.dumps(response['Item'], default=str))
        
        # Mark as read if not already
        if message.get('status') == MessageStatusEnum.NEW:
            contact_messages_table.update_item(
                Key={'id': message_id},
                UpdateExpression="SET #status = :status, updated_at = :updated_at",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":status": MessageStatusEnum.READ,
                    ":updated_at": datetime.now().isoformat()
                }
            )
            message['status'] = MessageStatusEnum.READ
        
        return message
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.put("/contact/messages/{message_id}", response_model=Dict[str, Any])
async def update_contact_message(
    message_id: str,
    update_data: ContactMessageUpdate,
    current_user: dict = Depends(get_admin_user)
):
    """
    Update contact message.
    Requires admin permissions.
    """
    try:
        # Check if message exists
        response = contact_messages_table.get_item(Key={'id': message_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact message not found"
            )
        
        # Prepare update data
        update_fields = update_data.dict(exclude_unset=True)
        update_fields['updated_at'] = datetime.now().isoformat()
        update_fields['updated_by'] = current_user.get('username', 'admin')
        
        # Build update expression
        update_expression = "SET "
        expression_values = {}
        expression_names = {}
        
        for key, value in update_fields.items():
            if key == 'status':
                update_expression += "#status = :status, "
                expression_names["#status"] = "status"
                expression_values[":status"] = value
            else:
                update_expression += f"{key} = :{key}, "
                expression_values[f":{key}"] = value
        
        update_expression = update_expression.rstrip(", ")
        
        # Update item
        update_kwargs = {
            'Key': {'id': message_id},
            'UpdateExpression': update_expression,
            'ExpressionAttributeValues': expression_values,
            'ReturnValues': "ALL_NEW"
        }
        
        if expression_names:
            update_kwargs['ExpressionAttributeNames'] = expression_names
        
        response = contact_messages_table.update_item(**update_kwargs)
        
        # Convert DynamoDB item
        message = json.loads(json.dumps(response['Attributes'], default=str))
        return message
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.delete("/contact/messages/{message_id}")
async def delete_contact_message(
    message_id: str,
    current_user: dict = Depends(get_admin_user)
):
    """
    Delete contact message.
    Requires admin permissions.
    """
    try:
        # Check if message exists
        response = contact_messages_table.get_item(Key={'id': message_id})
        if 'Item' not in response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact message not found"
            )
        
        # Delete the message
        contact_messages_table.delete_item(Key={'id': message_id})
        
        return {"message": "Contact message deleted successfully"}
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


@router.get("/contact/stats", response_model=Dict[str, Any])
async def get_contact_stats(
    current_user: dict = Depends(get_admin_user)
):
    """
    Get contact statistics.
    Requires admin permissions.
    """
    try:
        # Scan all messages to calculate stats
        response = contact_messages_table.scan()
        messages = response.get('Items', [])
        
        # Calculate statistics
        total_messages = len(messages)
        new_messages = len([m for m in messages if m.get('status') == MessageStatusEnum.NEW])
        in_progress = len([m for m in messages if m.get('status') == MessageStatusEnum.IN_PROGRESS])
        resolved = len([m for m in messages if m.get('status') == MessageStatusEnum.RESOLVED])
        
        # Count by inquiry type
        inquiry_counts = {}
        for message in messages:
            inquiry_type = message.get('inquiry_type', 'general')
            inquiry_counts[inquiry_type] = inquiry_counts.get(inquiry_type, 0) + 1
        
        # Count by priority
        priority_counts = {}
        for message in messages:
            priority = message.get('priority', 'normal')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        # Recent messages (last 7 days)
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        recent_messages = len([
            m for m in messages 
            if m.get('created_at', '') >= seven_days_ago
        ])
        
        return {
            "total_messages": total_messages,
            "new_messages": new_messages,
            "in_progress": in_progress,
            "resolved_messages": resolved,
            "recent_messages_7_days": recent_messages,
            "inquiry_type_breakdown": inquiry_counts,
            "priority_breakdown": priority_counts,
            "response_rate": round((resolved / total_messages * 100) if total_messages > 0 else 0, 2)
        }
        
    except ClientError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )