import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from botocore.exceptions import ClientError
from app.services.s3_service import S3Service, get_s3_settings, s3_service

class TestS3Settings:
    """Test cases for S3 configuration settings"""
    
    def test_s3_settings_default_values(self):
        """Test that S3 settings have proper default values"""
        settings = get_s3_settings()
        assert settings.aws_region == "us-east-1"
        assert settings.s3_bucket_name == "vitachecklabs-reports"
        assert settings.s3_reports_prefix == "lab-reports/"

class TestS3Service:
    """Test cases for S3 service functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.s3_service = S3Service()
    
    @pytest.mark.asyncio
    async def test_upload_file_success(self):
        """Test successful file upload to S3"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.put_object.return_value = None
            
            file_content = b"test file content"
            file_name = "test_report.pdf"
            
            result = await self.s3_service.upload_file(file_content, file_name, "application/pdf")
            
            assert result is not None
            assert result.startswith("lab-reports/")
            assert result.endswith(".pdf")
            mock_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_failure(self):
        """Test file upload failure"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.put_object.side_effect = ClientError(
                error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
                operation_name='PutObject'
            )
            
            file_content = b"test file content"
            file_name = "test_report.pdf"
            
            result = await self.s3_service.upload_file(file_content, file_name)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_download_file_success(self):
        """Test successful file download from S3"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_response = {
                'Body': Mock()
            }
            mock_response['Body'].read.return_value = b"downloaded file content"
            mock_client.get_object.return_value = mock_response
            
            object_key = "lab-reports/test-file.pdf"
            result = await self.s3_service.download_file(object_key)
            
            assert result == b"downloaded file content"
            mock_client.get_object.assert_called_once_with(
                Bucket=self.s3_service.bucket_name, 
                Key=object_key
            )

    @pytest.mark.asyncio
    async def test_download_file_failure(self):
        """Test file download failure"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.get_object.side_effect = ClientError(
                error_response={'Error': {'Code': 'NoSuchKey', 'Message': 'Key not found'}},
                operation_name='GetObject'
            )
            
            object_key = "lab-reports/nonexistent-file.pdf"
            result = await self.s3_service.download_file(object_key)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_file_success(self):
        """Test successful file deletion from S3"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.delete_object.return_value = None
            
            object_key = "lab-reports/test-file.pdf"
            result = await self.s3_service.delete_file(object_key)
            
            assert result == True
            mock_client.delete_object.assert_called_once_with(
                Bucket=self.s3_service.bucket_name, 
                Key=object_key
            )

    @pytest.mark.asyncio
    async def test_delete_file_failure(self):
        """Test file deletion failure"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.delete_object.side_effect = ClientError(
                error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
                operation_name='DeleteObject'
            )
            
            object_key = "lab-reports/test-file.pdf"
            result = await self.s3_service.delete_file(object_key)
            
            assert result == False

    @pytest.mark.asyncio
    async def test_generate_presigned_url_success(self):
        """Test successful presigned URL generation"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_url = "https://s3.amazonaws.com/bucket/key?presigned=true"
            mock_client.generate_presigned_url.return_value = mock_url
            
            object_key = "lab-reports/test-file.pdf"
            result = await self.s3_service.generate_presigned_url(object_key, 1800)
            
            assert result == mock_url
            mock_client.generate_presigned_url.assert_called_once_with(
                'get_object',
                Params={'Bucket': self.s3_service.bucket_name, 'Key': object_key},
                ExpiresIn=1800
            )

    @pytest.mark.asyncio
    async def test_generate_presigned_url_failure(self):
        """Test presigned URL generation failure"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.generate_presigned_url.side_effect = ClientError(
                error_response={'Error': {'Code': 'AccessDenied', 'Message': 'Access Denied'}},
                operation_name='GeneratePresignedUrl'
            )
            
            object_key = "lab-reports/test-file.pdf"
            result = await self.s3_service.generate_presigned_url(object_key)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_check_bucket_exists_success(self):
        """Test successful bucket existence check"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.head_bucket.return_value = None
            
            result = await self.s3_service.check_bucket_exists()
            
            assert result == True
            mock_client.head_bucket.assert_called_once_with(Bucket=self.s3_service.bucket_name)

    @pytest.mark.asyncio
    async def test_check_bucket_exists_failure(self):
        """Test bucket existence check failure"""
        with patch.object(self.s3_service, 'client') as mock_client:
            mock_client.head_bucket.side_effect = ClientError(
                error_response={'Error': {'Code': 'NoSuchBucket', 'Message': 'Bucket not found'}},
                operation_name='HeadBucket'
            )
            
            result = await self.s3_service.check_bucket_exists()
            
            assert result == False

    def test_s3_service_initialization(self):
        """Test S3 service initialization"""
        service = S3Service()
        assert service.client is not None
        assert service.bucket_name == "vitachecklabs-reports"
        assert service.reports_prefix == "lab-reports/"

class TestS3ServiceIntegration:
    """Integration tests for S3 service"""
    
    def test_global_s3_service_instance(self):
        """Test that global s3_service instance is properly initialized"""
        assert s3_service is not None
        assert isinstance(s3_service, S3Service)
        assert s3_service.client is not None

if __name__ == "__main__":
    pytest.main([__file__])