from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "VitaCheckLabs API"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./test.db"
    DATABASE_ECHO: bool = False
    
    # JWT Authentication
    SECRET_KEY: str = "development_secret_key_change_in_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []
    
    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
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


settings = Settings()