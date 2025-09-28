from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "VitaCheckLabs API"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database  
    DATABASE_URL: str = "dynamodb://us-east-1"
    DATABASE_ECHO: bool = False
    DATABASE_TYPE: str = "dynamodb"
    
    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    
    # S3 Configuration
    S3_BUCKET_NAME: str = "default-bucket"
    S3_REGION: str = "us-east-1"
    S3_REPORTS_PREFIX: str = "lab-reports/"
    
    # DynamoDB Configuration
    DYNAMODB_USERS_TABLE: str = "vitachecklabs-users"
    DYNAMODB_LAB_TESTS_TABLE: str = "vitachecklabs-lab-tests"
    DYNAMODB_REPORTS_TABLE: str = "vitachecklabs-reports"
    DYNAMODB_BOOKINGS_TABLE: str = "vitachecklabs-bookings"
    DYNAMODB_REPORT_EXPLANATIONS_TABLE: str = "vitachecklabs-report-explanations"
    DYNAMODB_AI_RULES_TABLE: str = "vitachecklabs-ai-rules"
    DYNAMODB_AGENT_AUDIT_TABLE: str = "vitachecklabs-agent-audit"
    DYNAMODB_REMINDERS_TABLE: str = "vitachecklabs-reminders"
    
    # JWT Authentication
    SECRET_KEY: str = "development_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI/OpenAI Configuration
    OPENAI_API_KEY: str = ""
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # CORS
    BACKEND_CORS_ORIGINS: str = "*"
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins as a list"""
        if self.BACKEND_CORS_ORIGINS == "*":
            return ["*"]
        elif self.BACKEND_CORS_ORIGINS.startswith("[") and self.BACKEND_CORS_ORIGINS.endswith("]"):
            import json
            return json.loads(self.BACKEND_CORS_ORIGINS)
        else:
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]
    
    # File Upload
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "jpg", "jpeg", "png"]
    
    # Logging
    LOG_LEVEL: str = "DEBUG"
    
    @validator("ALLOWED_EXTENSIONS", pre=True)
    def parse_allowed_extensions(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            # Handle JSON string format like '["pdf", "jpg"]'
            if v.startswith("[") and v.endswith("]"):
                import json
                return json.loads(v)
            # Handle comma-separated format like 'pdf,jpg,png'
            return [ext.strip() for ext in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()