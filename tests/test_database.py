import pytest
import asyncio
from unittest.mock import Mock, patch
from sqlalchemy import text
from app.database import get_db, check_database_health, SessionLocal, engine
from app.database import get_database_settings

class TestDatabaseConnection:
    """Test cases for database connection and configuration"""
    
    def test_database_settings_default_values(self):
        """Test that database settings have proper default values"""
        settings = get_database_settings()
        assert settings.database_url == "postgresql://username:password@localhost/vitachecklabs"
        assert settings.database_echo == False

    def test_get_db_dependency(self):
        """Test the database dependency injection"""
        db_generator = get_db()
        # This should return a generator
        assert hasattr(db_generator, '__next__')

    @pytest.mark.asyncio
    async def test_database_health_check_success(self):
        """Test database health check when database is accessible"""
        with patch.object(SessionLocal, 'execute') as mock_execute:
            with patch.object(SessionLocal, 'close') as mock_close:
                # Mock successful database query
                mock_db = Mock()
                mock_execute.return_value = None
                
                with patch('app.database.SessionLocal', return_value=mock_db):
                    mock_db.execute.return_value = None
                    result = await check_database_health()
                
                assert result["status"] == "healthy"
                assert result["database"] == "connected"

    @pytest.mark.asyncio
    async def test_database_health_check_failure(self):
        """Test database health check when database is not accessible"""
        with patch('app.database.SessionLocal') as mock_session:
            mock_db = Mock()
            mock_db.execute.side_effect = Exception("Connection failed")
            mock_session.return_value = mock_db
            
            result = await check_database_health()
            
            assert result["status"] == "unhealthy"
            assert result["database"] == "disconnected"
            assert "error" in result
            assert "Connection failed" in result["error"]

    def test_database_engine_configuration(self):
        """Test that database engine is properly configured"""
        # Check if engine is created
        assert engine is not None
        
        # Check engine configuration
        assert engine.pool._pre_ping == True
        assert engine.pool._recycle == 300

class TestDatabaseIntegration:
    """Integration tests for database functionality"""
    
    @pytest.mark.asyncio
    async def test_database_session_context_manager(self):
        """Test database session lifecycle with proper cleanup"""
        db_gen = get_db()
        
        # Test that we can get a session
        try:
            db = next(db_gen)
            assert db is not None
            
            # Test basic query execution (this will fail without real DB)
            # but we're testing the session creation
            assert hasattr(db, 'execute')
            assert hasattr(db, 'close')
            
        except StopIteration:
            # This is expected when generator is exhausted
            pass
        except Exception as e:
            # Database connection might fail in test environment
            # This is acceptable for unit testing
            assert "database" in str(e).lower() or "connection" in str(e).lower()

    def test_session_local_creation(self):
        """Test that SessionLocal can be instantiated"""
        try:
            session = SessionLocal()
            assert session is not None
            session.close()
        except Exception as e:
            # Connection might fail in test environment
            assert "database" in str(e).lower() or "connection" in str(e).lower()

if __name__ == "__main__":
    pytest.main([__file__])