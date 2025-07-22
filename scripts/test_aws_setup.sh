#!/bin/bash

# Test AWS CLI Setup
# Run this script to verify AWS CLI is working correctly

echo "🧪 Testing AWS CLI Setup"
echo "========================"

# Navigate to project directory
cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Test AWS CLI installation
echo "1. Testing AWS CLI installation..."
if python -m awscli --version &> /dev/null; then
    echo "   ✅ AWS CLI installed successfully"
    python -m awscli --version
else
    echo "   ❌ AWS CLI not found"
    exit 1
fi

echo ""

# Test AWS credentials
echo "2. Testing AWS credentials..."
if python -m awscli sts get-caller-identity &> /dev/null; then
    echo "   ✅ AWS credentials configured correctly"
    python -m awscli sts get-caller-identity
else
    echo "   ❌ AWS credentials not configured or invalid"
    echo "   Please run: python -m awscli configure"
    exit 1
fi

echo ""

# Test boto3
echo "3. Testing boto3 Python library..."
if python -c "import boto3; print('boto3 version:', boto3.__version__)" &> /dev/null; then
    echo "   ✅ boto3 installed successfully"
    python -c "import boto3; print('boto3 version:', boto3.__version__)"
else
    echo "   ❌ boto3 not found"
    exit 1
fi

echo ""
echo "🎉 AWS Setup Complete!"
echo "======================"
echo ""
echo "You can now run the DynamoDB migration:"
echo "bash scripts/migrate.sh"