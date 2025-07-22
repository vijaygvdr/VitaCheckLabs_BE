#!/bin/bash

# DynamoDB Table Creation Script for VitaCheckLabs
# Run this first to create all required tables

REGION="us-east-1"

# Navigate to project root and activate virtual environment
cd "$(dirname "$0")/.."
source venv/bin/activate

# Set AWS CLI command
AWS_CLI="python -m awscli"

echo "Creating DynamoDB tables for VitaCheckLabs..."

# Create Users Table
echo "Creating vitachecklabs-users table..."
$AWS_CLI dynamodb create-table \
    --table-name vitachecklabs-users \
    --attribute-definitions \
        AttributeName=user_id,AttributeType=S \
        AttributeName=email,AttributeType=S \
        AttributeName=username,AttributeType=S \
    --key-schema \
        AttributeName=user_id,KeyType=HASH \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --global-secondary-indexes \
        IndexName=email-index,KeySchema='[{AttributeName=email,KeyType=HASH}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=5}' \
        IndexName=username-index,KeySchema='[{AttributeName=username,KeyType=HASH}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=5}' \
    --region $REGION

# Wait for Users table to be active
echo "Waiting for Users table to be active..."
$AWS_CLI dynamodb wait table-exists --table-name vitachecklabs-users --region $REGION

# Create Lab Tests Table
echo "Creating vitachecklabs-lab-tests table..."
$AWS_CLI dynamodb create-table \
    --table-name vitachecklabs-lab-tests \
    --attribute-definitions \
        AttributeName=test_id,AttributeType=S \
        AttributeName=code,AttributeType=S \
        AttributeName=category,AttributeType=S \
        AttributeName=price,AttributeType=N \
    --key-schema \
        AttributeName=test_id,KeyType=HASH \
    --provisioned-throughput \
        ReadCapacityUnits=10,WriteCapacityUnits=2 \
    --global-secondary-indexes \
        IndexName=code-index,KeySchema='[{AttributeName=code,KeyType=HASH}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=1}' \
        IndexName=category-price-index,KeySchema='[{AttributeName=category,KeyType=HASH},{AttributeName=price,KeyType=RANGE}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=1}' \
    --region $REGION

# Wait for Lab Tests table to be active
echo "Waiting for Lab Tests table to be active..."
$AWS_CLI dynamodb wait table-exists --table-name vitachecklabs-lab-tests --region $REGION

# Create Reports Table
echo "Creating vitachecklabs-reports table..."
$AWS_CLI dynamodb create-table \
    --table-name vitachecklabs-reports \
    --attribute-definitions \
        AttributeName=report_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=lab_test_id,AttributeType=S \
        AttributeName=status,AttributeType=S \
        AttributeName=created_at,AttributeType=S \
        AttributeName=report_number,AttributeType=S \
    --key-schema \
        AttributeName=report_id,KeyType=HASH \
    --provisioned-throughput \
        ReadCapacityUnits=15,WriteCapacityUnits=10 \
    --global-secondary-indexes \
        IndexName=user-status-index,KeySchema='[{AttributeName=user_id,KeyType=HASH},{AttributeName=created_at,KeyType=RANGE}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=10,WriteCapacityUnits=5}' \
        IndexName=test-status-index,KeySchema='[{AttributeName=lab_test_id,KeyType=HASH},{AttributeName=status,KeyType=RANGE}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=2}' \
        IndexName=report-number-index,KeySchema='[{AttributeName=report_number,KeyType=HASH}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=1}' \
    --region $REGION

# Wait for Reports table to be active
echo "Waiting for Reports table to be active..."
$AWS_CLI dynamodb wait table-exists --table-name vitachecklabs-reports --region $REGION

# Create Bookings Table
echo "Creating vitachecklabs-bookings table..."
$AWS_CLI dynamodb create-table \
    --table-name vitachecklabs-bookings \
    --attribute-definitions \
        AttributeName=booking_id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=test_id,AttributeType=S \
        AttributeName=appointment_date,AttributeType=S \
        AttributeName=booking_reference,AttributeType=S \
    --key-schema \
        AttributeName=booking_id,KeyType=HASH \
    --provisioned-throughput \
        ReadCapacityUnits=10,WriteCapacityUnits=8 \
    --global-secondary-indexes \
        IndexName=user-date-index,KeySchema='[{AttributeName=user_id,KeyType=HASH},{AttributeName=appointment_date,KeyType=RANGE}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=8,WriteCapacityUnits=4}' \
        IndexName=test-date-index,KeySchema='[{AttributeName=test_id,KeyType=HASH},{AttributeName=appointment_date,KeyType=RANGE}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=2}' \
        IndexName=reference-index,KeySchema='[{AttributeName=booking_reference,KeyType=HASH}]',Projection='{ProjectionType=ALL}',ProvisionedThroughput='{ReadCapacityUnits=5,WriteCapacityUnits=2}' \
    --region $REGION

# Wait for Bookings table to be active
echo "Waiting for Bookings table to be active..."
$AWS_CLI dynamodb wait table-exists --table-name vitachecklabs-bookings --region $REGION

echo "All DynamoDB tables created successfully!"
echo "You can now proceed with data migration."