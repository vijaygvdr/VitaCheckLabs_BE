#!/bin/bash

# Complete DynamoDB Migration Script
# This script will create tables, export data, and upload to DynamoDB

set -e  # Exit on any error

REGION="us-east-1"
SCRIPTS_DIR="scripts"

echo "🚀 Starting VitaCheckLabs DynamoDB Migration"
echo "=============================================="

# Navigate to project root and activate virtual environment
cd "$(dirname "$0")/.."
source venv/bin/activate

# Set AWS CLI alias
AWS_CLI="python -m awscli"

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check if AWS CLI is installed and configured
if ! $AWS_CLI --version &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI first."
    exit 1
fi

# Check AWS credentials
if ! $AWS_CLI sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run 'python -m awscli configure' first."
    exit 1
fi

echo "✅ AWS CLI configured and credentials found"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

echo "✅ Python 3 found"

# Check if boto3 is installed
if ! python3 -c "import boto3" &> /dev/null; then
    echo "❌ boto3 not found in virtual environment"
    exit 1
fi

echo "✅ boto3 available"

# Check if database file exists
if [ ! -f "test.db" ]; then
    echo "❌ SQLite database 'test.db' not found in current directory"
    echo "Please ensure you're running this from the project root directory"
    exit 1
fi

echo "✅ SQLite database found"

# Make scripts executable
chmod +x scripts/*.sh scripts/*.py

echo ""
echo "🏗️  Step 1: Creating DynamoDB Tables"
echo "====================================="

# Create DynamoDB tables
echo "Creating tables in AWS DynamoDB..."
bash $SCRIPTS_DIR/create-tables.sh

if [ $? -eq 0 ]; then
    echo "✅ DynamoDB tables created successfully"
else
    echo "❌ Failed to create DynamoDB tables"
    exit 1
fi

echo ""
echo "📤 Step 2: Exporting SQLite Data"
echo "================================"

# Export SQLite data
echo "Exporting data from SQLite database..."
python3 $SCRIPTS_DIR/export_sqlite_data.py

if [ $? -eq 0 ]; then
    echo "✅ Data exported successfully"
else
    echo "❌ Failed to export SQLite data"
    exit 1
fi

echo ""
echo "📥 Step 3: Uploading to DynamoDB"
echo "================================"

# Upload to DynamoDB
echo "Uploading data to DynamoDB..."
python3 $SCRIPTS_DIR/upload_to_dynamodb.py

if [ $? -eq 0 ]; then
    echo "✅ Data uploaded successfully"
else
    echo "❌ Failed to upload data to DynamoDB"
    exit 1
fi

echo ""
echo "🎉 Migration Complete!"
echo "======================"
echo ""
echo "Next Steps:"
echo "1. Update your application to use DynamoDB instead of SQLite"
echo "2. Update environment variables:"
echo "   DATABASE_URL=dynamodb://us-east-1"
echo "   AWS_REGION=us-east-1"
echo "3. Test your application with the migrated data"
echo "4. Deploy to AWS ECS/Fargate"
echo ""
echo "Migration data saved in: migration_data/"
echo "Keep this directory as backup until you verify everything works"
echo ""
echo "Estimated DynamoDB cost: $0-5/month (within free tier limits)"