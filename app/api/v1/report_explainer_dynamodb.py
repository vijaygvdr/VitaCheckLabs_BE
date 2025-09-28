"""
Report Explainer API endpoints using DynamoDB
Replaces SQLAlchemy-based report explainer with DynamoDB version
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from app.core.deps_dynamodb import get_current_active_user
from app.services.dynamodb_service import report_explanation_service, report_service
from app.schemas.report_explanation import (
    ReportExplanationRequest,
    ReportExplanationResponse,
    ReportExplanationSummary,
    BatchExplanationRequest,
    BatchExplanationResponse,
    ProcessingStatus,
    AbnormalValuesFilter
)
from app.services.report_explainer_service import report_explainer_service as ai_service
import asyncio
import os
import json
from datetime import datetime

router = APIRouter()


async def process_report_explanation_background(report_id: str, explanation_id: str):
    """Background task to process report explanation using DynamoDB."""
    try:
        # Get the explanation record
        explanation = report_explanation_service.get_explanation_by_id(explanation_id)
        if not explanation:
            return

        # Get the associated report from S3/DynamoDB
        report = report_service.get_report_by_id(report_id)
        if not report:
            report_explanation_service.update_explanation(explanation_id, {
                'processing_status': 'failed',
                'error_message': 'Report not found'
            })
            return

        # Mark as processing
        report_explanation_service.update_explanation(explanation_id, {
            'processing_status': 'processing'
        })

        # Process the report using AI service
        start_time = datetime.utcnow()

        # Extract report file path or get from S3
        file_path = report.get('s3_file_key') or report.get('s3_key') or report.get('file_path')
        if not file_path:
            report_explanation_service.update_explanation(explanation_id, {
                'processing_status': 'failed',
                'error_message': 'Report file path not found'
            })
            return

        # Download file from S3 to temporary location for processing
        import boto3
        import tempfile
        import os
        from app.core.config import settings

        s3_client = boto3.client('s3', region_name=settings.AWS_REGION)

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file_path = temp_file.name

        try:
            # Download from S3
            s3_client.download_file(settings.S3_BUCKET_NAME, file_path, temp_file_path)

            # Use the AI service to process the report
            result = await ai_service.process_report(file_path=temp_file_path)
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Convert floats to Decimal for DynamoDB compatibility
        from decimal import Decimal
        import json

        def convert_floats_to_decimal(obj):
            """Recursively convert float values to Decimal for DynamoDB."""
            if isinstance(obj, dict):
                return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_floats_to_decimal(item) for item in obj]
            elif isinstance(obj, float):
                return Decimal(str(obj))
            else:
                return obj

        # Update with successful results
        abnormal_values = convert_floats_to_decimal(list(result.get('abnormal_findings', {}).values()))
        extracted_data = convert_floats_to_decimal(result.get('parsed_values', {}))

        report_explanation_service.update_explanation(explanation_id, {
            'processing_status': 'completed',
            'patient_summary': result.get('summaries', {}).get('patient_summary', ''),
            'clinician_summary': result.get('summaries', {}).get('clinician_summary', ''),
            'abnormal_values': abnormal_values,
            'extracted_data': extracted_data,
            'processing_time_seconds': Decimal(str(processing_time)),
            'ai_model_used': 'gpt-4o-mini'
        })

    except Exception as e:
        # Update with error
        report_explanation_service.update_explanation(explanation_id, {
            'processing_status': 'failed',
            'error_message': str(e)
        })


@router.post("/{report_id}/explain", response_model=ReportExplanationResponse, status_code=status.HTTP_201_CREATED)
async def create_report_explanation(
    report_id: str,
    request: ReportExplanationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Create an AI explanation for a report.
    Users can only explain their own reports unless they are admin.
    """
    report_id_str = report_id

    # Check if report exists and user has access
    report = report_service.get_report_by_id(report_id_str)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    # Check user permissions
    if current_user.get('role') != 'admin' and report.get('user_id') != current_user.get('user_id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only explain your own reports"
        )

    # Check if explanation already exists
    existing_explanation = report_explanation_service.get_explanation_by_report_id(report_id_str)
    if existing_explanation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explanation already exists for this report"
        )

    # Create explanation record
    explanation_data = {
        'report_id': report_id_str,
        'user_id': current_user.get('user_id'),
        'processing_status': 'pending'
    }

    explanation = report_explanation_service.create_explanation(explanation_data)

    # Start background processing
    background_tasks.add_task(
        process_report_explanation_background,
        report_id_str,
        explanation['explanation_id']
    )

    return ReportExplanationResponse(
        id=explanation['explanation_id'],
        report_id=report_id,
        processing_status=ProcessingStatus(explanation['processing_status']),
        patient_summary=explanation.get('patient_summary', ''),
        clinician_summary=explanation.get('clinician_summary', ''),
        abnormal_values=explanation.get('abnormal_values', []),
        extracted_data=explanation.get('extracted_data', {}),
        ai_model_used=explanation.get('ai_model_used', ''),
        processing_time_seconds=explanation.get('processing_time_seconds', 0),
        created_at=explanation.get('created_at'),
        updated_at=explanation.get('updated_at')
    )


@router.get("/{report_id}/explanation", response_model=ReportExplanationResponse)
async def get_report_explanation(
    report_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get the explanation for a specific report.
    Users can only access explanations for their own reports unless they are admin.
    """
    report_id_str = report_id

    explanation = report_explanation_service.get_explanation_by_report_id(report_id_str)
    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explanation not found"
        )

    # Check user permissions
    if current_user.get('role') != 'admin' and explanation.get('user_id') != current_user.get('user_id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own explanations"
        )

    return ReportExplanationResponse(
        id=explanation['explanation_id'],
        report_id=report_id,
        processing_status=ProcessingStatus(explanation['processing_status']),
        patient_summary=explanation.get('patient_summary', ''),
        clinician_summary=explanation.get('clinician_summary', ''),
        abnormal_values=explanation.get('abnormal_values', []),
        extracted_data=explanation.get('extracted_data', {}),
        ai_model_used=explanation.get('ai_model_used', ''),
        processing_time_seconds=explanation.get('processing_time_seconds', 0),
        created_at=explanation.get('created_at'),
        updated_at=explanation.get('updated_at'),
        error_message=explanation.get('error_message', '')
    )


@router.get("/", response_model=List[ReportExplanationSummary])
async def list_report_explanations(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[ProcessingStatus] = Query(None, description="Filter by processing status"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    List report explanations.
    Users see only their own explanations unless they are admin.
    """
    if current_user.get('role') == 'ADMIN':
        # Admin can see all explanations
        explanations = report_explanation_service.get_all_explanations(limit=per_page)
    else:
        # Regular users see only their own
        explanations = report_explanation_service.get_explanations_by_user(
            current_user.get('user_id'),
            limit=per_page
        )

    # Filter by status if provided
    if status:
        explanations = [e for e in explanations if e.get('processing_status') == status.value]

    # Convert to summary format
    summaries = []
    for explanation in explanations:
        summaries.append(ReportExplanationSummary(
            id=explanation['explanation_id'],
            report_id=explanation['report_id'],
            processing_status=ProcessingStatus(explanation['processing_status']),
            ai_model_used=explanation.get('ai_model_used', ''),
            processing_time_seconds=explanation.get('processing_time_seconds', 0),
            created_at=explanation.get('created_at'),
            updated_at=explanation.get('updated_at')
        ))

    return summaries


@router.get("/{report_id}/explanation/summaries")
async def get_explanation_summaries(
    report_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get only the summaries from a report explanation.
    Useful for displaying just the patient and clinician summaries.
    """
    report_id_str = report_id

    explanation = report_explanation_service.get_explanation_by_report_id(report_id_str)
    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explanation not found"
        )

    # Check user permissions
    if current_user.get('role') != 'admin' and explanation.get('user_id') != current_user.get('user_id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own explanations"
        )

    return {
        "patient_summary": explanation.get('patient_summary', ''),
        "clinician_summary": explanation.get('clinician_summary', ''),
        "processing_status": explanation.get('processing_status', 'pending')
    }


@router.get("/{report_id}/explanation/abnormal-values")
async def get_abnormal_values(
    report_id: str,
    filter_data: Optional[AbnormalValuesFilter] = None,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get abnormal values from a report explanation with optional filtering.
    """
    report_id_str = report_id

    explanation = report_explanation_service.get_explanation_by_report_id(report_id_str)
    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explanation not found"
        )

    # Check user permissions
    if current_user.get('role') != 'admin' and explanation.get('user_id') != current_user.get('user_id'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own explanations"
        )

    abnormal_values = explanation.get('abnormal_values', [])

    # Apply filtering if provided
    if filter_data:
        if filter_data.severity_levels:
            abnormal_values = [
                av for av in abnormal_values
                if av.get('severity') in filter_data.severity_levels
            ]

    return {
        "abnormal_values": abnormal_values,
        "total_count": len(abnormal_values)
    }


@router.delete("/{report_id}/explanation", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report_explanation(
    report_id: str,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Delete a report explanation.
    Admin only feature.
    """
    if current_user.get('role') != 'ADMIN':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    report_id_str = report_id
    explanation = report_explanation_service.get_explanation_by_report_id(report_id_str)

    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Explanation not found"
        )

    success = report_explanation_service.delete_explanation(explanation['explanation_id'])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete explanation"
        )


@router.post("/batch-explain", response_model=BatchExplanationResponse)
async def batch_create_explanations(
    request: BatchExplanationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Create explanations for multiple reports in batch.
    Admin only feature.
    """
    if current_user.get('role') != 'ADMIN':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    created_explanations = []
    failed_reports = []

    for report_id in request.report_ids:
        try:
            report_id_str = report_id

            # Check if report exists
            report = report_service.get_report_by_id(report_id_str)
            if not report:
                failed_reports.append({"report_id": report_id, "reason": "Report not found"})
                continue

            # Check if explanation already exists
            existing_explanation = report_explanation_service.get_explanation_by_report_id(report_id_str)
            if existing_explanation:
                failed_reports.append({"report_id": report_id, "reason": "Explanation already exists"})
                continue

            # Create explanation record
            explanation_data = {
                'report_id': report_id_str,
                'user_id': report.get('user_id'),  # Use report owner's user_id
                'processing_status': 'pending'
            }

            explanation = report_explanation_service.create_explanation(explanation_data)
            created_explanations.append(explanation['explanation_id'])

            # Start background processing
            background_tasks.add_task(
                process_report_explanation_background,
                report_id_str,
                explanation['explanation_id']
            )

        except Exception as e:
            failed_reports.append({"report_id": report_id, "reason": str(e)})

    return BatchExplanationResponse(
        created_count=len(created_explanations),
        failed_count=len(failed_reports),
        created_explanation_ids=created_explanations,
        failed_reports=failed_reports
    )


@router.get("/stats/overview")
async def get_explanation_stats(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get statistics about report explanations.
    Users see stats for their own explanations, admins see global stats.
    """
    if current_user.get('role') == 'ADMIN':
        # Admin sees global stats
        all_explanations = report_explanation_service.get_all_explanations(limit=1000)
        explanations = all_explanations
    else:
        # Users see their own stats
        explanations = report_explanation_service.get_explanations_by_user(
            current_user.get('user_id'),
            limit=1000
        )

    # Calculate statistics
    total_count = len(explanations)
    status_counts = {}
    total_processing_time = 0
    successful_count = 0

    for explanation in explanations:
        status = explanation.get('processing_status', 'pending')
        status_counts[status] = status_counts.get(status, 0) + 1

        if status == 'completed':
            successful_count += 1
            total_processing_time += explanation.get('processing_time_seconds', 0)

    avg_processing_time = total_processing_time / successful_count if successful_count > 0 else 0

    return {
        "total_explanations": total_count,
        "status_breakdown": status_counts,
        "success_rate": (successful_count / total_count * 100) if total_count > 0 else 0,
        "average_processing_time_seconds": round(avg_processing_time, 2)
    }