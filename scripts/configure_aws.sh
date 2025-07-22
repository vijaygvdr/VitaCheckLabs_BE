#!/bin/bash

# AWS CLI Configuration Helper Script
# This script helps configure AWS CLI with your credentials

echo "🔧 AWS CLI Configuration Helper"
echo "==============================="

# Navigate to project directory
cd "$(dirname "$0")/.."

# Activate virtual environment
source venv/bin/activate

# Create alias for AWS CLI
echo "Creating AWS CLI alias..."
alias aws='python -m awscli'

echo ""
echo "📋 You need to provide the following information:"
echo "1. AWS Access Key ID (from IAM user)"
echo "2. AWS Secret Access Key (from IAM user)"
echo "3. Default region: us-east-1 (recommended)"
echo "4. Default output format: json (recommended)"
echo ""

# Run AWS configure
echo "Starting AWS CLI configuration..."
python -m awscli configure

echo ""
echo "✅ AWS CLI configuration completed!"
echo ""
echo "💡 To make the AWS alias permanent, add this to your ~/.bashrc:"
echo "alias aws='cd /mnt/c/Users/vijay/Cursor\ Projects/VitaCheckLabs_BE && source venv/bin/activate && python -m awscli'"