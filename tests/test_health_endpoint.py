import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from main import app

client = TestClient(app)

class TestHealthEndpoints:
    """Test cases for health check endpoints"""
    
    def test_root_endpoint(self):
        """Test the root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "VitaCheckLabs API is running"
        assert data["version"] == "1.0.0"

    @patch('app.database.check_database_health')
    @patch('app.services.s3_service.s3_service.check_bucket_exists')
    def test_health_endpoint_all_healthy(self, mock_s3_check, mock_db_check):
        """Test health endpoint when all services are healthy"""
        # Mock database health check
        mock_db_check.return_value = {
            "status": "healthy",
            "database": "connected"
        }
        
        # Mock S3 health check
        mock_s3_check.return_value = True
        
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "healthy"
        assert data["database"]["database"] == "connected"
        assert data["s3"]["status"] == "healthy"

    @patch('app.database.check_database_health')
    @patch('app.services.s3_service.s3_service.check_bucket_exists')
    def test_health_endpoint_database_unhealthy(self, mock_s3_check, mock_db_check):
        """Test health endpoint when database is unhealthy"""
        # Mock database health check failure
        mock_db_check.return_value = {
            "status": "unhealthy",
            "database": "disconnected",
            "error": "Connection timeout"
        }
        
        # Mock S3 health check success
        mock_s3_check.return_value = True
        
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "unhealthy"
        assert data["database"]["database"] == "disconnected"
        assert "error" in data["database"]
        assert data["s3"]["status"] == "healthy"

    @patch('app.database.check_database_health')
    @patch('app.services.s3_service.s3_service.check_bucket_exists')
    def test_health_endpoint_s3_unhealthy(self, mock_s3_check, mock_db_check):
        """Test health endpoint when S3 is unhealthy"""
        # Mock database health check success
        mock_db_check.return_value = {
            "status": "healthy",
            "database": "connected"
        }
        
        # Mock S3 health check failure
        mock_s3_check.return_value = False
        
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "healthy"
        assert data["s3"]["status"] == "unhealthy"

    @patch('app.database.check_database_health')
    @patch('app.services.s3_service.s3_service.check_bucket_exists')
    def test_health_endpoint_all_unhealthy(self, mock_s3_check, mock_db_check):
        """Test health endpoint when all services are unhealthy"""
        # Mock database health check failure
        mock_db_check.return_value = {
            "status": "unhealthy",
            "database": "disconnected",
            "error": "Connection failed"
        }
        
        # Mock S3 health check failure
        mock_s3_check.return_value = False
        
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["database"]["status"] == "unhealthy"
        assert data["s3"]["status"] == "unhealthy"

class TestHealthEndpointIntegration:
    """Integration tests for health endpoints"""
    
    def test_health_endpoint_structure(self):
        """Test that health endpoint returns proper structure"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        assert "status" in data
        assert "database" in data
        assert "s3" in data
        
        # Check database section structure
        assert isinstance(data["database"], dict)
        assert "status" in data["database"]
        
        # Check S3 section structure
        assert isinstance(data["s3"], dict)
        assert "status" in data["s3"]

if __name__ == "__main__":
    pytest.main([__file__])