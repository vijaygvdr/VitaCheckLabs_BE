#!/usr/bin/env python3
"""
Setup IAM roles for ECS deployment using Python
"""

import boto3
import json
import os

def setup_iam_roles():
    """Create necessary IAM roles for ECS deployment"""
    
    iam = boto3.client('iam')
    sts = boto3.client('sts')
    ssm = boto3.client('ssm')
    
    account_id = sts.get_caller_identity()['Account']
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    print("🔐 Setting up IAM roles for ECS deployment...")
    
    # 1. ECS Task Execution Role
    print("Creating ECS Task Execution Role...")
    
    execution_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        iam.get_role(RoleName='ecsTaskExecutionRole')
        print("✅ ECS Task Execution Role already exists")
    except iam.exceptions.NoSuchEntityException:
        # Create the role
        iam.create_role(
            RoleName='ecsTaskExecutionRole',
            AssumeRolePolicyDocument=json.dumps(execution_trust_policy),
            Description='ECS Task Execution Role for VitaCheckLabs'
        )
        
        # Attach AWS managed policy
        iam.attach_role_policy(
            RoleName='ecsTaskExecutionRole',
            PolicyArn='arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'
        )
        print("✅ ECS Task Execution Role created")
    
    # 2. ECS Task Role
    print("Creating ECS Task Role...")
    
    task_trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    task_policy = {
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
                    f"arn:aws:dynamodb:{region}:{account_id}:table/vitachecklabs-*",
                    f"arn:aws:dynamodb:{region}:{account_id}:table/vitachecklabs-*/index/*"
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
                "Resource": f"arn:aws:ssm:{region}:{account_id}:parameter/vitachecklabs/*"
            }
        ]
    }
    
    try:
        iam.get_role(RoleName='ecsTaskRole')
        print("✅ ECS Task Role already exists")
    except iam.exceptions.NoSuchEntityException:
        # Create the role
        iam.create_role(
            RoleName='ecsTaskRole',
            AssumeRolePolicyDocument=json.dumps(task_trust_policy),
            Description='ECS Task Role for VitaCheckLabs application'
        )
        
        # Create and attach custom policy
        try:
            iam.create_policy(
                PolicyName='VitaCheckLabsTaskPolicy',
                PolicyDocument=json.dumps(task_policy),
                Description='Policy for VitaCheckLabs ECS tasks to access DynamoDB and S3'
            )
        except iam.exceptions.EntityAlreadyExistsException:
            pass  # Policy already exists
        
        iam.attach_role_policy(
            RoleName='ecsTaskRole',
            PolicyArn=f'arn:aws:iam::{account_id}:policy/VitaCheckLabsTaskPolicy'
        )
        print("✅ ECS Task Role created")
    
    # 3. Create SSM parameter for JWT secret
    print("Creating SSM parameter for JWT secret...")
    try:
        ssm.get_parameter(Name='/vitachecklabs/jwt/secret-key')
        print("✅ JWT secret parameter already exists")
    except ssm.exceptions.ParameterNotFound:
        import secrets
        jwt_secret = secrets.token_hex(32)
        
        ssm.put_parameter(
            Name='/vitachecklabs/jwt/secret-key',
            Value=f'production_secret_key_{jwt_secret}',
            Type='SecureString',
            Description='JWT secret key for VitaCheckLabs API'
        )
        print("✅ JWT secret parameter created")
    
    print("\n🎉 IAM setup completed successfully!")
    print("\nCreated roles:")
    print("  • ecsTaskExecutionRole - For ECS to manage containers")
    print("  • ecsTaskRole - For app to access DynamoDB and S3")
    print("\nNext: Build and deploy the Docker container")

if __name__ == "__main__":
    setup_iam_roles()