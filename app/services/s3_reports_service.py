"""
Enhanced S3 service for handling lab report uploads and downloads
Integrates with DynamoDB to store file metadata
"""

import boto3
import uuid
import os
from datetime import datetime, timedelta
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, Dict, Any, BinaryIO
import mimetypes
from pathlib import Path

class S3ReportsService:
    """Service for managing lab report files in S3"""
    
    def __init__(self, bucket_name: str = "vitachecklabs-reports-poc-v2", region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.region = region
        
        try:
            self.s3_client = boto3.client('s3', region_name=region)
            self.s3_resource = boto3.resource('s3', region_name=region)
            self.bucket = self.s3_resource.Bucket(bucket_name)
        except NoCredentialsError:
            raise Exception("AWS credentials not configured. Please run 'aws configure'")
    
    def generate_file_key(self, user_id: str, report_id: str, filename: str) -> str:
        """Generate S3 key for report file with organized structure"""
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        
        # Clean filename
        clean_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        
        return f"lab-reports/{year}/{month}/reports/{user_id}/{report_id}/{timestamp}_{clean_filename}"
    
    def upload_report(
        self, 
        file_content: BinaryIO, 
        filename: str, 
        user_id: str, 
        report_id: str,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a report file to S3
        
        Args:
            file_content: File-like object with binary content
            filename: Original filename
            user_id: User ID for organization
            report_id: Report ID for organization
            content_type: MIME type (auto-detected if not provided)
            
        Returns:
            Dict with upload details including S3 key, URL, and metadata
        """
        try:
            # Auto-detect content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = 'application/octet-stream'
            
            # Generate S3 key
            s3_key = self.generate_file_key(user_id, report_id, filename)
            
            # Get file size
            file_content.seek(0, 2)  # Seek to end
            file_size = file_content.tell()
            file_content.seek(0)  # Reset to beginning
            
            # Upload metadata
            metadata = {
                'user_id': user_id,
                'report_id': report_id,
                'original_filename': filename,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'file_size': str(file_size)
            }
            
            # Upload to S3
            self.s3_client.upload_fileobj(
                file_content,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    'ContentType': content_type,
                    'Metadata': metadata,
                    'ServerSideEncryption': 'AES256'
                }
            )
            
            return {
                's3_key': s3_key,
                'bucket': self.bucket_name,
                'file_size': file_size,
                'content_type': content_type,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'success': True
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': f"AWS error: {str(e)}",
                'error_code': e.response['Error']['Code']
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Upload failed: {str(e)}"
            }
    
    def download_report(self, s3_key: str) -> Optional[bytes]:
        """
        Download a report file from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            File content as bytes, or None if error
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            raise e
    
    def generate_presigned_url(
        self, 
        s3_key: str, 
        operation: str = 'get_object',
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for secure file access
        
        Args:
            s3_key: S3 object key
            operation: 'get_object' for download, 'put_object' for upload
            expiration: URL expiration time in seconds (default 1 hour)
            
        Returns:
            Presigned URL string or None if error
        """
        try:
            if operation == 'get_object':
                params = {'Bucket': self.bucket_name, 'Key': s3_key}
            elif operation == 'put_object':
                params = {'Bucket': self.bucket_name, 'Key': s3_key}
            else:
                raise ValueError(f"Unsupported operation: {operation}")
            
            url = self.s3_client.generate_presigned_url(
                operation,
                Params=params,
                ExpiresIn=expiration
            )
            return url
            
        except ClientError:
            return None
    
    def delete_report(self, s3_key: str) -> bool:
        """
        Delete a report file from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False
    
    def list_user_reports(self, user_id: str, limit: int = 100) -> list:
        """
        List all reports for a specific user
        
        Args:
            user_id: User ID
            limit: Maximum number of files to return
            
        Returns:
            List of report file metadata
        """
        try:
            prefix = f"lab-reports/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=limit
            )
            
            reports = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Filter by user_id in the key path
                    if f"/{user_id}/" in obj['Key']:
                        reports.append({
                            's3_key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'filename': os.path.basename(obj['Key'])
                        })
            
            return reports
            
        except ClientError:
            return []
    
    def get_file_metadata(self, s3_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file in S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Metadata dictionary or None if error
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            
            return {
                'content_type': response.get('ContentType'),
                'content_length': response.get('ContentLength'),
                'last_modified': response.get('LastModified'),
                'metadata': response.get('Metadata', {}),
                'etag': response.get('ETag')
            }
            
        except ClientError:
            return None
    
    async def check_bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists and is accessible
        
        Returns:
            True if bucket exists and accessible, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            return False


# Convenience instance for easy import
s3_reports_service = S3ReportsService()


# Example usage functions for FastAPI integration
def upload_lab_report(file_content: BinaryIO, filename: str, user_id: str, report_id: str) -> Dict[str, Any]:
    """Upload a lab report and return S3 details for DynamoDB storage"""
    return s3_reports_service.upload_report(file_content, filename, user_id, report_id)

def get_report_download_url(s3_key: str, expiration: int = 3600) -> Optional[str]:
    """Get a presigned URL for downloading a report"""
    return s3_reports_service.generate_presigned_url(s3_key, 'get_object', expiration)

def get_report_upload_url(s3_key: str, expiration: int = 3600) -> Optional[str]:
    """Get a presigned URL for uploading a report"""
    return s3_reports_service.generate_presigned_url(s3_key, 'put_object', expiration)