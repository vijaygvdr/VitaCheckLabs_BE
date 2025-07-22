#!/usr/bin/env python3
"""
Upload exported JSON data to DynamoDB
This script takes the exported JSON files and uploads them to DynamoDB using boto3
"""

import json
import boto3
import time
from botocore.exceptions import ClientError
from pathlib import Path

# Configuration
REGION = "us-east-1"
INPUT_DIR = "migration_data"
BATCH_SIZE = 25  # DynamoDB batch_write_item limit

# Table mappings
TABLE_MAPPINGS = {
    "users": "vitachecklabs-users",
    "lab_tests": "vitachecklabs-lab-tests", 
    "reports": "vitachecklabs-reports",
    "bookings": "vitachecklabs-bookings"
}

def initialize_dynamodb():
    """Initialize DynamoDB client"""
    try:
        dynamodb = boto3.resource('dynamodb', region_name=REGION)
        print(f"Connected to DynamoDB in region {REGION}")
        return dynamodb
    except Exception as e:
        print(f"Error connecting to DynamoDB: {e}")
        return None

def convert_to_dynamodb_format(item):
    """Convert Python types to DynamoDB format"""
    def convert_value(value):
        if value is None or value == "":
            return ""  # DynamoDB doesn't store null values
        elif isinstance(value, bool):
            return value
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            return value
        elif isinstance(value, dict):
            return json.dumps(value) if value else "{}"
        elif isinstance(value, list):
            return json.dumps(value) if value else "[]"
        else:
            return str(value)
    
    return {key: convert_value(value) for key, value in item.items() if key != "original_id"}

def upload_batch(dynamodb, table_name, items):
    """Upload a batch of items to DynamoDB"""
    if not items:
        return True
    
    table = dynamodb.Table(table_name)
    
    try:
        # Prepare batch write request
        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=convert_to_dynamodb_format(item))
        
        print(f"  ✓ Uploaded batch of {len(items)} items to {table_name}")
        return True
        
    except ClientError as e:
        print(f"  ✗ Error uploading batch to {table_name}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error uploading to {table_name}: {e}")
        return False

def upload_table_data(dynamodb, data_type, file_path):
    """Upload all data for a specific table"""
    table_name = TABLE_MAPPINGS[data_type]
    
    print(f"\nUploading {data_type} to {table_name}...")
    
    try:
        with open(file_path, 'r') as f:
            items = json.load(f)
        
        if not items:
            print(f"  No data found in {file_path}")
            return True
        
        print(f"  Found {len(items)} items to upload")
        
        # Upload in batches
        success_count = 0
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
        
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            
            print(f"  Uploading batch {batch_num}/{total_batches}...")
            
            if upload_batch(dynamodb, table_name, batch):
                success_count += len(batch)
            else:
                print(f"  Failed to upload batch {batch_num}")
            
            # Small delay to avoid throttling
            time.sleep(0.1)
        
        print(f"  ✓ Successfully uploaded {success_count}/{len(items)} items")
        return success_count == len(items)
        
    except FileNotFoundError:
        print(f"  ✗ File not found: {file_path}")
        return False
    except json.JSONDecodeError:
        print(f"  ✗ Invalid JSON in file: {file_path}")
        return False
    except Exception as e:
        print(f"  ✗ Error uploading {data_type}: {e}")
        return False

def verify_upload(dynamodb, data_type):
    """Verify data was uploaded correctly"""
    table_name = TABLE_MAPPINGS[data_type]
    table = dynamodb.Table(table_name)
    
    try:
        response = table.scan(Select='COUNT')
        count = response['Count']
        print(f"  {table_name}: {count} items")
        return count
    except Exception as e:
        print(f"  Error verifying {table_name}: {e}")
        return 0

def main():
    """Main upload function"""
    print("Starting DynamoDB data upload...")
    
    # Check if input directory exists
    if not Path(INPUT_DIR).exists():
        print(f"Input directory {INPUT_DIR} not found!")
        print("Please run export_sqlite_data.py first")
        return
    
    # Initialize DynamoDB
    dynamodb = initialize_dynamodb()
    if not dynamodb:
        return
    
    # Upload data in dependency order (no foreign key constraints in DynamoDB)
    upload_order = ["users", "lab_tests", "reports", "bookings"]
    
    success_count = 0
    
    for data_type in upload_order:
        file_path = Path(INPUT_DIR) / f"{data_type}.json"
        
        if file_path.exists():
            if upload_table_data(dynamodb, data_type, file_path):
                success_count += 1
            else:
                print(f"Failed to upload {data_type}")
        else:
            print(f"Skipping {data_type} - file not found")
    
    print(f"\n{'='*50}")
    print("MIGRATION SUMMARY")
    print(f"{'='*50}")
    print(f"Successfully uploaded: {success_count}/{len(upload_order)} tables")
    
    if success_count == len(upload_order):
        print("✓ All data migrated successfully!")
    else:
        print("✗ Some tables failed to migrate")
    
    # Verify upload
    print(f"\n{'='*50}")
    print("VERIFICATION")
    print(f"{'='*50}")
    
    for data_type in upload_order:
        verify_upload(dynamodb, data_type)
    
    print(f"\n{'='*50}")
    print("NEXT STEPS")
    print(f"{'='*50}")
    print("1. Update your application code to use DynamoDB")
    print("2. Test the application with migrated data")
    print("3. Update environment variables to point to DynamoDB")
    print("4. Deploy to AWS with DynamoDB configuration")

if __name__ == "__main__":
    main()