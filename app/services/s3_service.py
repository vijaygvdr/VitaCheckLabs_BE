import boto3
import os
from botocore.exceptions import ClientError
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import uuid

class S3Settings(BaseSettings):
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "vitachecklabs-reports"
    s3_reports_prefix: str = "lab-reports/"
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env

@lru_cache()
def get_s3_settings():
    return S3Settings()

class S3Service:
    def __init__(self):
        self.settings = get_s3_settings()
        self.client = boto3.client(
            's3',
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
            region_name=self.settings.aws_region
        )
        self.bucket_name = self.settings.s3_bucket_name
        self.reports_prefix = self.settings.s3_reports_prefix

    def upload_file(self, file_content: bytes, file_name: str, content_type: str = "application/octet-stream") -> Optional[str]:
        """
        Upload a file to S3 and return the object key
        """
        try:
            # Generate unique file name
            file_extension = file_name.split('.')[-1] if '.' in file_name else ''
            unique_filename = f"{uuid.uuid4().hex}.{file_extension}" if file_extension else str(uuid.uuid4().hex)
            object_key = f"{self.reports_prefix}{unique_filename}"
            
            # Upload file
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_content,
                ContentType=content_type
            )
            
            return object_key
        except ClientError as e:
            print(f"Error uploading file to S3: {e}")
            return None

    def download_file(self, object_key: str) -> Optional[bytes]:
        """
        Download a file from S3
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            return response['Body'].read()
        except ClientError as e:
            print(f"Error downloading file from S3: {e}")
            return None

    def delete_file(self, object_key: str) -> bool:
        """
        Delete a file from S3
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            print(f"Error deleting file from S3: {e}")
            return False

    def generate_presigned_url(self, object_key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for file download
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"Error generating presigned URL: {e}")
            return None

    def check_bucket_exists(self) -> bool:
        """
        Check if the S3 bucket exists and is accessible
        """
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError as e:
            print(f"Bucket {self.bucket_name} not accessible: {e}")
            return False

# Global S3 service instance
s3_service = S3Service()