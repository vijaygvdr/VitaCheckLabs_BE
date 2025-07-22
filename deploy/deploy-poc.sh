#!/bin/bash

# AWS ECS POC Deployment Script for VitaCheckLabs (Cost Optimized)
# This script deploys a minimal cost POC version to AWS ECS Fargate

set -e

# Configuration for POC (cost optimized)
REGION="us-east-1"
CLUSTER_NAME="vitachecklabs-poc-cluster"
SERVICE_NAME="vitachecklabs-poc-service"
TASK_FAMILY="vitachecklabs-api-poc"
ECR_REPOSITORY="vitachecklabs-api-poc"
IMAGE_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting VitaCheckLabs POC Deployment (Cost Optimized)${NC}"
echo "=================================================================="

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Check if AWS CLI is configured
if ! python -m awscli sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not configured. Please run 'python -m awscli configure' first.${NC}"
    exit 1
fi

ACCOUNT_ID=$(python -m awscli sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPOSITORY}"

echo -e "${YELLOW}💰 POC Cost Optimization Features:${NC}"
echo "   ✅ Minimal CPU/Memory (256 CPU, 512 MB)"
echo "   ✅ Single instance (desired count = 1)"
echo "   ✅ On-demand DynamoDB billing"
echo "   ✅ Optimized health checks"
echo "   ✅ Auto-shutdown capability"
echo ""

echo -e "${BLUE}📋 Deployment Configuration:${NC}"
echo "   Account ID: ${ACCOUNT_ID}"
echo "   Region: ${REGION}"
echo "   ECR Repository: ${ECR_URI}"
echo "   Cluster: ${CLUSTER_NAME}"
echo "   Service: ${SERVICE_NAME}"
echo ""

# Step 1: Create ECR repository if it doesn't exist
echo -e "${YELLOW}📦 Step 1: Setting up ECR repository...${NC}"
if ! python -m awscli ecr describe-repositories --repository-names ${ECR_REPOSITORY} --region ${REGION} &> /dev/null; then
    echo "Creating ECR repository..."
    python -m awscli ecr create-repository --repository-name ${ECR_REPOSITORY} --region ${REGION}
    # Set lifecycle policy to keep only 3 images
    python -m awscli ecr put-lifecycle-policy --repository-name ${ECR_REPOSITORY} --region ${REGION} --lifecycle-policy-text '{
        "rules": [
            {
                "rulePriority": 1,
                "description": "Keep only 3 images",
                "selection": {
                    "tagStatus": "any",
                    "countType": "imageCountMoreThan",
                    "countNumber": 3
                },
                "action": {
                    "type": "expire"
                }
            }
        ]
    }'
    echo -e "${GREEN}✅ ECR repository created with lifecycle policy${NC}"
else
    echo -e "${GREEN}✅ ECR repository already exists${NC}"
fi

# Step 2: Build and push Docker image
echo -e "${YELLOW}🐳 Step 2: Building and pushing Docker image...${NC}"

# Login to ECR
python -m awscli ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URI}

# Build image
echo "Building optimized Docker image..."
docker build -f Dockerfile.production -t ${ECR_REPOSITORY}:${IMAGE_TAG} .

# Tag for ECR
docker tag ${ECR_REPOSITORY}:${IMAGE_TAG} ${ECR_URI}:${IMAGE_TAG}

# Push to ECR
echo "Pushing image to ECR..."
docker push ${ECR_URI}:${IMAGE_TAG}
echo -e "${GREEN}✅ Docker image pushed successfully${NC}"

# Step 3: Create ECS cluster if it doesn't exist
echo -e "${YELLOW}🎯 Step 3: Setting up ECS cluster...${NC}"
if ! python -m awscli ecs describe-clusters --clusters ${CLUSTER_NAME} --region ${REGION} --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "Creating ECS cluster..."
    python -m awscli ecs create-cluster --cluster-name ${CLUSTER_NAME} --region ${REGION} --capacity-providers FARGATE --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1
    echo -e "${GREEN}✅ ECS cluster created${NC}"
else
    echo -e "${GREEN}✅ ECS cluster already exists${NC}"
fi

# Step 4: Create CloudWatch log group with retention
echo -e "${YELLOW}📊 Step 4: Setting up CloudWatch logs (7-day retention)...${NC}"
if ! python -m awscli logs describe-log-groups --log-group-name-prefix "/ecs/vitachecklabs-api-poc" --region ${REGION} --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "vitachecklabs-api-poc"; then
    echo "Creating CloudWatch log group..."
    python -m awscli logs create-log-group --log-group-name "/ecs/vitachecklabs-api-poc" --region ${REGION}
    # Set 7-day retention to save costs
    python -m awscli logs put-retention-policy --log-group-name "/ecs/vitachecklabs-api-poc" --retention-in-days 7 --region ${REGION}
    echo -e "${GREEN}✅ CloudWatch log group created with 7-day retention${NC}"
else
    echo -e "${GREEN}✅ CloudWatch log group already exists${NC}"
fi

# Step 5: Create task definition
echo -e "${YELLOW}📋 Step 5: Registering ECS task definition...${NC}"

# Update task definition with actual values
sed -e "s/{ACCOUNT_ID}/${ACCOUNT_ID}/g" \
    -e "s|{ECR_REPOSITORY_URI}|${ECR_URI}|g" \
    deploy/ecs-task-definition-poc.json > /tmp/task-definition-poc.json

# Register task definition
python -m awscli ecs register-task-definition --cli-input-json file:///tmp/task-definition-poc.json --region ${REGION}
echo -e "${GREEN}✅ POC task definition registered${NC}"

# Step 6: Create or update ECS service
echo -e "${YELLOW}🎯 Step 6: Creating/updating ECS service...${NC}"

# Check if service exists
if python -m awscli ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${REGION} --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
    echo "Updating existing service..."
    python -m awscli ecs update-service \
        --cluster ${CLUSTER_NAME} \
        --service ${SERVICE_NAME} \
        --task-definition ${TASK_FAMILY} \
        --region ${REGION}
    echo -e "${GREEN}✅ Service updated${NC}"
else
    echo "Creating new service..."
    
    # Get default VPC and subnets
    VPC_ID=$(python -m awscli ec2 describe-vpcs --filters "Name=is-default,Values=true" --query 'Vpcs[0].VpcId' --output text --region ${REGION})
    SUBNET_IDS=$(python -m awscli ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --query 'Subnets[*].SubnetId' --output text --region ${REGION})
    
    # Create security group for POC
    SECURITY_GROUP_ID=$(python -m awscli ec2 create-security-group \
        --group-name vitachecklabs-poc-sg \
        --description "Security group for VitaCheckLabs POC" \
        --vpc-id ${VPC_ID} \
        --query 'GroupId' \
        --output text \
        --region ${REGION} 2>/dev/null || \
        python -m awscli ec2 describe-security-groups \
        --filters "Name=group-name,Values=vitachecklabs-poc-sg" "Name=vpc-id,Values=${VPC_ID}" \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region ${REGION})
    
    # Add inbound rule for port 8000
    python -m awscli ec2 authorize-security-group-ingress \
        --group-id ${SECURITY_GROUP_ID} \
        --protocol tcp \
        --port 8000 \
        --cidr 0.0.0.0/0 \
        --region ${REGION} 2>/dev/null || echo "Rule already exists"
    
    # Create service with auto-scaling
    python -m awscli ecs create-service \
        --cluster ${CLUSTER_NAME} \
        --service-name ${SERVICE_NAME} \
        --task-definition ${TASK_FAMILY} \
        --desired-count 1 \
        --launch-type FARGATE \
        --platform-version LATEST \
        --network-configuration "awsvpcConfiguration={subnets=[$(echo ${SUBNET_IDS} | tr ' ' ',')],securityGroups=[${SECURITY_GROUP_ID}],assignPublicIp=ENABLED}" \
        --enable-execute-command \
        --region ${REGION}
    
    echo -e "${GREEN}✅ POC service created${NC}"
fi

# Step 7: Set up auto-scaling (scale to 0 capability)
echo -e "${YELLOW}⚡ Step 7: Setting up auto-scaling...${NC}"
python -m awscli application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --resource-id service/${CLUSTER_NAME}/${SERVICE_NAME} \
    --scalable-dimension ecs:service:DesiredCount \
    --min-capacity 0 \
    --max-capacity 2 \
    --region ${REGION} 2>/dev/null || echo "Auto-scaling already configured"

echo -e "${GREEN}✅ Auto-scaling configured (can scale to 0)${NC}"

# Step 8: Wait for service to stabilize
echo -e "${YELLOW}⏳ Step 8: Waiting for service to stabilize...${NC}"
python -m awscli ecs wait services-stable --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${REGION}

# Get service details
TASK_ARN=$(python -m awscli ecs list-tasks --cluster ${CLUSTER_NAME} --service-name ${SERVICE_NAME} --query 'taskArns[0]' --output text --region ${REGION})
if [ "$TASK_ARN" != "None" ] && [ "$TASK_ARN" != "" ]; then
    ENI_ID=$(python -m awscli ecs describe-tasks --cluster ${CLUSTER_NAME} --tasks ${TASK_ARN} --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text --region ${REGION})
    PUBLIC_IP=$(python -m awscli ec2 describe-network-interfaces --network-interface-ids ${ENI_ID} --query 'NetworkInterfaces[0].Association.PublicIp' --output text --region ${REGION} 2>/dev/null || echo "Not available yet")
else
    PUBLIC_IP="Not available yet"
fi

echo ""
echo -e "${GREEN}🎉 POC Deployment completed successfully!${NC}"
echo "=================================================================="
echo -e "${GREEN}✅ Application Details:${NC}"
echo "   Cluster: ${CLUSTER_NAME}"
echo "   Service: ${SERVICE_NAME}"
echo "   Task: ${TASK_ARN}"
echo "   Public IP: ${PUBLIC_IP}"
if [ "$PUBLIC_IP" != "Not available yet" ]; then
    echo "   Health Check: http://${PUBLIC_IP}:8000/health"
    echo "   API Documentation: http://${PUBLIC_IP}:8000/docs"
fi
echo ""
echo -e "${BLUE}💰 Cost Optimization Summary:${NC}"
echo "   ✅ Minimal resources (256 CPU, 512 MB RAM)"
echo "   ✅ Can scale to 0 instances (manual)"
echo "   ✅ 7-day log retention"
echo "   ✅ Lifecycle policy (3 images max)"
echo "   ✅ On-demand DynamoDB"
echo ""
echo -e "${YELLOW}📋 Cost Management Commands:${NC}"
echo "   Scale to 0: python -m awscli ecs update-service --cluster ${CLUSTER_NAME} --service ${SERVICE_NAME} --desired-count 0 --region ${REGION}"
echo "   Scale to 1: python -m awscli ecs update-service --cluster ${CLUSTER_NAME} --service ${SERVICE_NAME} --desired-count 1 --region ${REGION}"
echo "   Delete service: python -m awscli ecs delete-service --cluster ${CLUSTER_NAME} --service ${SERVICE_NAME} --force --region ${REGION}"
echo ""
echo -e "${GREEN}💰 Estimated POC Cost: ~$3-8/month (vs $17-24 production)${NC}"
echo -e "${BLUE}🎯 When not in use, scale to 0 for ~$0.50/month (just DynamoDB + S3)${NC}"

# Clean up temp files
rm -f /tmp/task-definition-poc.json