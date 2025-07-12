# VitaCheckLabs Backend API

FastAPI backend for VitaCheckLabs - a comprehensive lab testing platform.

## Features

- **Lab Tests**: Browse and book laboratory tests
- **Reports**: Upload, view, and manage test reports
- **Company Info**: Access company information and services
- **Authentication**: JWT-based user authentication
- **Role-based Access**: Admin and user roles

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd VitaCheckLabs_BE
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run Development Server**
   ```bash
   uvicorn main:app --reload
   ```

## API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

## Project Structure

```
VitaCheckLabs_BE/
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Core configuration
│   ├── models/          # Database models
│   ├── schemas/         # Pydantic schemas
│   └── services/        # Business logic
├── tests/               # Test files
├── main.py             # FastAPI application entry point
└── requirements.txt    # Python dependencies
```

## Development Status

- ✅ VIT-21: Project structure setup
- ⏳ VIT-22: Database connection and migrations
- ⏳ VIT-23: Database models
- ⏳ VIT-24: Authentication system
- ⏳ VIT-25: Lab Tests API
- ⏳ VIT-26: Reports API
- ⏳ VIT-27: Company API
- ⏳ VIT-28: Validation and error handling
- ⏳ VIT-29: Documentation and tests