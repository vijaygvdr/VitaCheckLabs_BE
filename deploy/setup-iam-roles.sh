#!/bin/bash

# Setup IAM roles for ECS deployment
# This script creates the necessary IAM roles and policies

set -e

REGION="us-east-1"

echo "🔐 Setting up IAM roles for ECS deployment..."

# 1. Create ECS Task Execution Role
echo "Creating ECS Task Execution Role..."

# Check if role exists
if ! aws iam get-role --role-name ecsTaskExecutionRole &> /dev/null; then
    # Create trust policy
    cat > /tmp/ecs-task-execution-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create the role
    aws iam create-role \
        --role-name ecsTaskExecutionRole \
        --assume-role-policy-document file:///tmp/ecs-task-execution-trust-policy.json

    # Attach AWS managed policy
    aws iam attach-role-policy \
        --role-name ecsTaskExecutionRole \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

    echo "✅ ECS Task Execution Role created"
else
    echo "✅ ECS Task Execution Role already exists"
fi

# 2. Create ECS Task Role (for DynamoDB and S3 access)
echo "Creating ECS Task Role..."

if ! aws iam get-role --role-name ecsTaskRole &> /dev/null; then
    # Create trust policy
    cat > /tmp/ecs-task-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    # Create the role
    aws iam create-role \
        --role-name ecsTaskRole \
        --assume-role-policy-document file:///tmp/ecs-task-trust-policy.json

    # Create policy for DynamoDB and S3 access
    cat > /tmp/ecs-task-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:BatchGetItem",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:${REGION}:*:table/vitachecklabs-*",
        "arn:aws:dynamodb:${REGION}:*:table/vitachecklabs-*/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::vitachecklabs-reports-poc-v2",
        "arn:aws:s3:::vitachecklabs-reports-poc-v2/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath"
      ],
      "Resource": "arn:aws:ssm:${REGION}:*:parameter/vitachecklabs/*"
    }
  ]
}
EOF

    # Create and attach the policy
    aws iam create-policy \
        --policy-name VitaCheckLabsTaskPolicy \
        --policy-document file:///tmp/ecs-task-policy.json

    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    aws iam attach-role-policy \
        --role-name ecsTaskRole \
        --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/VitaCheckLabsTaskPolicy

    echo "✅ ECS Task Role created"
else
    echo "✅ ECS Task Role already exists"
fi

# 3. Create Systems Manager parameter for JWT secret
echo "Creating SSM parameter for JWT secret..."
if ! aws ssm get-parameter --name "/vitachecklabs/jwt/secret-key" &> /dev/null; then
    aws ssm put-parameter \
        --name "/vitachecklabs/jwt/secret-key" \
        --value "production_secret_key_$(openssl rand -hex 32)" \
        --type "SecureString" \
        --description "JWT secret key for VitaCheckLabs API"
    echo "✅ JWT secret parameter created"
else
    echo "✅ JWT secret parameter already exists"
fi

# Clean up temp files
rm -f /tmp/ecs-task-*.json

echo "🎉 IAM setup completed successfully!"
echo ""
echo "Created roles:"
echo "  • ecsTaskExecutionRole - For ECS to manage containers"
echo "  • ecsTaskRole - For app to access DynamoDB and S3"
echo ""
echo "Next: Run ./deploy.sh to deploy the application"