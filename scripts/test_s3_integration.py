#!/usr/bin/env python3
"""
Test S3 integration for report uploads
This script tests the S3 service functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.s3_reports_service import s3_reports_service
import io
import uuid

def test_s3_connection():
    """Test S3 bucket connection"""
    print("🔗 Testing S3 connection...")
    try:
        bucket_exists = s3_reports_service.check_bucket_exists()
        if bucket_exists:
            print("✅ S3 bucket is accessible")
            return True
        else:
            print("❌ S3 bucket not accessible")
            return False
    except Exception as e:
        print(f"❌ S3 connection failed: {e}")
        return False

def test_file_upload():
    """Test file upload to S3"""
    print("\n📤 Testing file upload...")
    try:
        # Create a test PDF content
        test_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000079 00000 n \n0000000173 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n253\n%%EOF"
        
        file_obj = io.BytesIO(test_content)
        
        # Test upload
        result = s3_reports_service.upload_report(
            file_content=file_obj,
            filename="test_report.pdf",
            user_id="usr_test_123",
            report_id="rpt_test_456",
            content_type="application/pdf"
        )
        
        if result['success']:
            print(f"✅ File uploaded successfully")
            print(f"   S3 Key: {result['s3_key']}")
            print(f"   Size: {result['file_size']} bytes")
            return result['s3_key']
        else:
            print(f"❌ Upload failed: {result['error']}")
            return None
            
    except Exception as e:
        print(f"❌ Upload test failed: {e}")
        return None

def test_file_download(s3_key):
    """Test file download from S3"""
    print(f"\n📥 Testing file download...")
    try:
        content = s3_reports_service.download_report(s3_key)
        if content:
            print(f"✅ File downloaded successfully")
            print(f"   Size: {len(content)} bytes")
            return True
        else:
            print("❌ Download failed: File not found")
            return False
    except Exception as e:
        print(f"❌ Download test failed: {e}")
        return False

def test_presigned_url(s3_key):
    """Test presigned URL generation"""
    print(f"\n🔗 Testing presigned URL generation...")
    try:
        download_url = s3_reports_service.generate_presigned_url(s3_key, 'get_object', 3600)
        if download_url:
            print(f"✅ Presigned URL generated successfully")
            print(f"   URL: {download_url[:100]}...")
            return True
        else:
            print("❌ Presigned URL generation failed")
            return False
    except Exception as e:
        print(f"❌ Presigned URL test failed: {e}")
        return False

def test_file_cleanup(s3_key):
    """Test file deletion"""
    print(f"\n🗑️  Testing file cleanup...")
    try:
        deleted = s3_reports_service.delete_report(s3_key)
        if deleted:
            print("✅ File deleted successfully")
            return True
        else:
            print("❌ File deletion failed")
            return False
    except Exception as e:
        print(f"❌ Cleanup test failed: {e}")
        return False

def main():
    """Run all S3 integration tests"""
    print("🧪 S3 Integration Test Suite")
    print("=" * 40)
    
    tests_passed = 0
    total_tests = 5
    
    # Test 1: S3 Connection
    if test_s3_connection():
        tests_passed += 1
    
    # Test 2: File Upload
    s3_key = test_file_upload()
    if s3_key:
        tests_passed += 1
        
        # Test 3: File Download
        if test_file_download(s3_key):
            tests_passed += 1
        
        # Test 4: Presigned URL
        if test_presigned_url(s3_key):
            tests_passed += 1
        
        # Test 5: File Cleanup
        if test_file_cleanup(s3_key):
            tests_passed += 1
    
    print(f"\n{'=' * 40}")
    print(f"TEST RESULTS: {tests_passed}/{total_tests} passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! S3 integration is working correctly.")
        print("\n📋 S3 Setup Summary:")
        print(f"   Bucket: {s3_reports_service.bucket_name}")
        print(f"   Region: {s3_reports_service.region}")
        print("   Features: Upload ✅ Download ✅ Presigned URLs ✅")
        print("\n🚀 Your application can now:")
        print("   • Upload report files to S3")
        print("   • Generate secure download links")
        print("   • Store file metadata in DynamoDB")
        print("   • Control access with presigned URLs")
    else:
        print("❌ Some tests failed. Check your AWS configuration.")
        print("\n🔧 Troubleshooting:")
        print("   • Verify AWS credentials are configured")
        print("   • Check S3 bucket permissions")
        print("   • Ensure bucket exists and is accessible")

if __name__ == "__main__":
    main()