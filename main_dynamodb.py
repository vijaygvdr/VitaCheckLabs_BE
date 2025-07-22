"""
FastAPI application entry point using DynamoDB
This is the DynamoDB version of the application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api_dynamodb import api_router
import os

# Load DynamoDB environment variables
if os.path.exists('.env.dynamodb'):
    from dotenv import load_dotenv
    load_dotenv('.env.dynamodb')

# Create app instance
app = FastAPI(
    title=settings.PROJECT_NAME + " (DynamoDB)",
    version="1.0.0",
    description="VitaCheckLabs API using DynamoDB and S3 for scalable cloud deployment",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware - Allow all origins for POC
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for POC
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "message": "VitaCheckLabs API is running (DynamoDB + S3)", 
        "version": "1.0.0",
        "database": "DynamoDB",
        "storage": "S3"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for DynamoDB + S3."""
    import boto3
    from botocore.exceptions import ClientError
    
    health_status = {
        "status": "healthy",
        "database": {"status": "unknown"},
        "s3": {"status": "unknown"},
        "timestamp": "2024-12-19T18:30:00Z"
    }
    
    try:
        # Check DynamoDB health
        dynamodb = boto3.client('dynamodb', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        dynamodb.describe_table(TableName='vitachecklabs-users')
        health_status["database"] = {"status": "healthy", "type": "DynamoDB"}
    except ClientError:
        health_status["database"] = {"status": "unhealthy", "type": "DynamoDB"}
        health_status["status"] = "unhealthy"
    
    try:
        # Check S3 health
        s3 = boto3.client('s3', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        s3.head_bucket(Bucket=os.getenv('S3_BUCKET_NAME', 'vitachecklabs-reports-poc-v2'))
        health_status["s3"] = {"status": "healthy", "bucket": os.getenv('S3_BUCKET_NAME')}
    except ClientError:
        health_status["s3"] = {"status": "unhealthy", "bucket": os.getenv('S3_BUCKET_NAME')}
        health_status["status"] = "unhealthy"
    
    return health_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)