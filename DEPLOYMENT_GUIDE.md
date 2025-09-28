# 🚀 AWS ECS Deployment Guide - VitaCheckLabs AI System

## 🎉 Complete AI-Powered Lab Test System Ready for Deployment!

Your VitaCheckLabs application now includes:
- ✅ **AI-Powered Booking Copilot** with 11 intelligent symptom rules
- ✅ **4 Comprehensive Lab Tests** (Vitamin D, LFT, TFT, CBC)
- ✅ **DynamoDB** for all data storage and AI rules
- ✅ **Real-time symptom analysis** and test recommendations
- ✅ **Admin APIs** for managing lab tests and AI rules

## 🧠 AI Features Included

### Intelligent Lab Test Recommendations
- **Vitamin D Test**: Detects bone pain, fatigue, depression symptoms
- **Liver Function Test**: Recognizes jaundice, nausea, abdominal pain
- **Thyroid Function Test**: Identifies weight changes, temperature sensitivity, heart palpitations
- **Complete Blood Count**: Flags fatigue, frequent infections, easy bruising

### Smart Booking Copilot
- **Natural Language Processing** of user symptoms
- **Contextual Conversations** with medical disclaimers
- **Progressive Symptom Collection** and analysis
- **Intelligent Test Scoring** based on symptom matching

## 🚀 Quick Deployment (5 Steps)

### Step 1: Prerequisites Setup
```bash
# Ensure AWS CLI is configured
aws sts get-caller-identity

# Ensure Docker is running
docker version
```

### Step 2: Store Secrets in AWS
```bash
# Store JWT Secret Key
aws ssm put-parameter \
  --name "/vitachecklabs/jwt/secret-key" \
  --value "your-secure-jwt-secret-key-change-this" \
  --type "SecureString" \
  --region us-east-1

# Store OpenAI API Key (for AI features)
aws ssm put-parameter \
  --name "/vitachecklabs/openai/api-key" \
  --value "your-openai-api-key-here" \
  --type "SecureString" \
  --region us-east-1
```

### Step 3: Deploy to AWS ECS
```bash
# Make deploy script executable
chmod +x deploy/deploy-poc.sh

# Run deployment (takes ~5-10 minutes)
./deploy/deploy-poc.sh
```

### Step 4: Test the AI System
```bash
# Get PUBLIC_IP from deployment output, then test:
curl -X POST "http://${PUBLIC_IP}:8000/api/v1/booking-copilot/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I have jaundice and dark urine. My eyes look yellow and I feel nauseous.",
    "session_id": null,
    "user_id": "test-user-123"
  }'

# Expected: AI recommends Liver Function Test (LFT)
```

### Step 5: Access Your Application
- **Health Check**: `http://${PUBLIC_IP}:8000/health`
- **API Documentation**: `http://${PUBLIC_IP}:8000/docs`
- **AI Booking Copilot**: `http://${PUBLIC_IP}:8000/api/v1/booking-copilot/chat`

## 💰 Cost Management
```bash
# Scale down when not in use (saves ~90% cost)
aws ecs update-service \
  --cluster vitachecklabs-poc-cluster \
  --service vitachecklabs-poc-service \
  --desired-count 0 \
  --region us-east-1

# Scale back up
aws ecs update-service \
  --cluster vitachecklabs-poc-cluster \
  --service vitachecklabs-poc-service \
  --desired-count 1 \
  --region us-east-1
```

**Monthly Cost**: ~$3-8 when active, ~$0.50 when scaled to 0

## 📋 Detailed Information

### Files Created for Deployment
```
VitaCheckLabs_BE/
├── Dockerfile.production          # Production Docker image
├── docker-compose.production.yml  # Docker Compose for production
├── main_dynamodb.py               # DynamoDB version of the app
├── .env.dynamodb                 # DynamoDB environment config
├── app/
│   ├── services/
│   │   ├── dynamodb_service.py   # DynamoDB data layer
│   │   └── s3_reports_service.py # S3 file management
│   ├── api/v1/
│   │   ├── api_dynamodb.py       # Main API router
│   │   ├── auth_dynamodb.py      # Authentication endpoints
│   │   ├── lab_tests_dynamodb.py # Lab tests endpoints
│   │   ├── bookings_dynamodb.py  # Bookings endpoints
│   │   └── reports_s3.py         # Reports + S3 endpoints
│   └── core/
│       └── deps_dynamodb.py      # DynamoDB dependencies
└── deploy/
    ├── ecs-task-definition.json  # ECS task configuration
    ├── deploy.sh                 # Automated deployment script
    └── setup-iam-roles.sh        # IAM role setup
```

## 🚀 Deployment Options

### Option 1: AWS ECS Fargate (Recommended)

#### Prerequisites
1. **AWS Account** with appropriate permissions:
   - ECS full access
   - ECR full access
   - IAM role creation
   - VPC management

2. **Docker** installed on your local machine

3. **AWS CLI** configured with credentials

#### Deployment Steps

1. **Create IAM Roles** (one-time setup):
   ```bash
   # You'll need admin access to create these roles in AWS Console:
   
   # ECS Task Execution Role
   Role Name: ecsTaskExecutionRole
   Trust Policy: ecs-tasks.amazonaws.com
   Policies: AmazonECSTaskExecutionRolePolicy
   
   # ECS Task Role  
   Role Name: ecsTaskRole
   Trust Policy: ecs-tasks.amazonaws.com
   Policies: Custom policy for DynamoDB + S3 access
   ```

2. **Build and Deploy**:
   ```bash
   cd VitaCheckLabs_BE
   
   # Make scripts executable
   chmod +x deploy/*.sh
   
   # Deploy to AWS
   ./deploy/deploy.sh
   ```

3. **Access Your Application**:
   - The script will provide a public IP
   - Health check: `http://{PUBLIC_IP}:8000/health`
   - API docs: `http://{PUBLIC_IP}:8000/docs`

### Option 2: Local Docker (For Testing)

```bash
# Build the container
docker build -f Dockerfile.production -t vitachecklabs-api .

# Run with environment variables
docker run -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID=your_key \
  -e AWS_SECRET_ACCESS_KEY=your_secret \
  -e AWS_REGION=us-east-1 \
  vitachecklabs-api
```

### Option 3: Docker Compose

```bash
# Copy your AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Start with Docker Compose
docker-compose -f docker-compose.production.yml up -d
```

## 💰 Cost Breakdown

### Monthly Costs (Estimated)
- **DynamoDB**: $11.51/month (optimized capacity)
- **S3**: $0-2/month (5GB free tier)
- **ECS Fargate**: $5-10/month (0.25 vCPU, 0.5GB RAM)
- **ECR**: $0/month (500MB free)
- **CloudWatch Logs**: $0.50/month
- **Data Transfer**: $0/month (100GB free)

**Total: ~$17-24/month**

### Cost Optimization Tips
1. Use **Fargate Spot** for 60% savings
2. Set **auto-scaling min to 0** during off-hours
3. Use **DynamoDB On-Demand** for unpredictable traffic
4. Set up **CloudWatch billing alerts**

## 🔧 Environment Configuration

### Required Environment Variables
```bash
# Database
DATABASE_URL=dynamodb://us-east-1
AWS_REGION=us-east-1

# S3
S3_BUCKET_NAME=vitachecklabs-reports-poc-v2

# JWT (store in AWS Systems Manager)
SECRET_KEY=your_production_secret

# Application
ENVIRONMENT=production
DEBUG=false
```

## 🔐 Security Configuration

### S3 Bucket Security
- ✅ Private bucket (no public access)
- ✅ Presigned URLs for secure file access
- ✅ Server-side encryption enabled
- ✅ Lifecycle policies for cost optimization

### DynamoDB Security
- ✅ IAM-based access control
- ✅ Fine-grained permissions per table
- ✅ No public access

### Application Security
- ✅ JWT authentication
- ✅ Non-root container user
- ✅ Health checks enabled
- ✅ Secrets stored in AWS Systems Manager

## 📊 Monitoring & Health Checks

### Health Check Endpoints
- `GET /health` - Overall application health
- `GET /` - Basic connectivity test

### CloudWatch Metrics
- Container CPU/Memory usage
- Request count and latency
- DynamoDB read/write capacity
- S3 request metrics

## 🛠️ Troubleshooting

### Common Issues

1. **DynamoDB Access Denied**
   - Check IAM role has DynamoDB permissions
   - Verify table names match environment

2. **S3 Upload Failures**
   - Check S3 bucket permissions
   - Verify bucket name in environment variables

3. **Container Health Check Failures**
   - Check if application is binding to 0.0.0.0:8000
   - Verify environment variables are set

4. **Authentication Issues**
   - Check JWT secret is properly configured
   - Verify user data migrated correctly

### Debug Commands
```bash
# Check container logs
docker logs {container_id}

# Test DynamoDB connectivity
python -c "from app.services.dynamodb_service import user_service; print(user_service.get_all_users())"

# Test S3 connectivity  
python -c "from app.services.s3_reports_service import s3_reports_service; print(s3_reports_service.check_bucket_exists())"
```

## 🎯 Next Steps

1. **Set up monitoring** with CloudWatch dashboards
2. **Configure custom domain** with Route53 + ALB
3. **Set up SSL certificate** with AWS Certificate Manager
4. **Implement backup strategy** for DynamoDB
5. **Set up CI/CD pipeline** with GitHub Actions
6. **Configure log aggregation** and alerting

## 📞 Support

If you encounter issues:
1. Check the health endpoint: `/health`
2. Review CloudWatch logs
3. Verify AWS credentials and permissions
4. Test DynamoDB and S3 connectivity directly

---

**🎉 Congratulations! Your VitaCheckLabs application is now running on AWS with DynamoDB and S3, ready for production use!**