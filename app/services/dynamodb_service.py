"""
DynamoDB service layer to replace SQLAlchemy ORM
Provides CRUD operations for all entities using DynamoDB
"""

import boto3
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
import json
import os

class DynamoDBService:
    """Base DynamoDB service with common operations"""
    
    def __init__(self, region_name: str = None):
        self.region = region_name or os.getenv('AWS_REGION', 'us-east-1')
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        
        # Initialize table references
        self.users_table = self.dynamodb.Table('vitachecklabs-users')
        self.lab_tests_table = self.dynamodb.Table('vitachecklabs-lab-tests')
        self.reports_table = self.dynamodb.Table('vitachecklabs-reports')
        self.bookings_table = self.dynamodb.Table('vitachecklabs-bookings')
    
    def _serialize_datetime(self, dt) -> str:
        """Convert datetime to ISO string"""
        if isinstance(dt, datetime):
            return dt.isoformat() + 'Z'
        return dt or ''
    
    def _deserialize_datetime(self, dt_str: str) -> Optional[datetime]:
        """Convert ISO string to datetime"""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            return None

class UserService(DynamoDBService):
    """User management service using DynamoDB"""
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email using GSI or scan as fallback"""
        try:
            # First try using GSI
            response = self.users_table.query(
                IndexName='email-index',
                KeyConditionExpression=Key('email').eq(email.lower())
            )
            items = response.get('Items', [])
            if items:
                return items[0]
        except ClientError:
            # Fallback to scan if GSI doesn't exist
            try:
                response = self.users_table.scan(
                    FilterExpression=Attr('email').eq(email.lower())
                )
                items = response.get('Items', [])
                return items[0] if items else None
            except ClientError:
                pass
        return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username using GSI or scan as fallback"""
        try:
            # First try using GSI
            response = self.users_table.query(
                IndexName='username-index',
                KeyConditionExpression=Key('username').eq(username.lower())
            )
            items = response.get('Items', [])
            if items:
                return items[0]
        except ClientError:
            # Fallback to scan if GSI doesn't exist
            try:
                response = self.users_table.scan(
                    FilterExpression=Attr('username').eq(username.lower())
                )
                items = response.get('Items', [])
                return items[0] if items else None
            except ClientError:
                pass
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            response = self.users_table.get_item(Key={'user_id': user_id})
            return response.get('Item')
        except ClientError:
            return None
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user"""
        user_id = f"usr_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'
        
        item = {
            'user_id': user_id,
            'email': user_data['email'].lower(),
            'username': user_data['username'].lower(),
            'password_hash': user_data['password_hash'],
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'phone_number': user_data.get('phone_number', ''),
            'role': user_data.get('role', 'user'),
            'is_active': user_data.get('is_active', True),
            'is_verified': user_data.get('is_verified', False),
            'created_at': now,
            'updated_at': now,
            'last_login': None
        }
        
        try:
            self.users_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create user: {str(e)}")
    
    def update_user(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """Update user data"""
        try:
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat() + 'Z'}
            
            for key, value in updates.items():
                if key not in ['user_id', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value
            
            self.users_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            return True
        except ClientError:
            return False
    
    def update_last_login(self, user_id: str) -> bool:
        """Update user's last login time"""
        try:
            self.users_table.update_item(
                Key={'user_id': user_id},
                UpdateExpression="SET last_login = :login_time",
                ExpressionAttributeValues={
                    ':login_time': datetime.utcnow().isoformat() + 'Z'
                }
            )
            return True
        except ClientError:
            return False

class LabTestService(DynamoDBService):
    """Lab test management service using DynamoDB"""
    
    def get_all_tests(self, is_active: bool = True) -> List[Dict[str, Any]]:
        """Get all lab tests"""
        try:
            if is_active:
                response = self.lab_tests_table.scan(
                    FilterExpression=Attr('is_active').eq(True)
                )
            else:
                response = self.lab_tests_table.scan()
            
            return response.get('Items', [])
        except ClientError:
            return []
    
    def get_test_by_id(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get lab test by ID"""
        try:
            response = self.lab_tests_table.get_item(Key={'test_id': test_id})
            return response.get('Item')
        except ClientError:
            return None
    
    def get_test_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Get lab test by code using GSI"""
        try:
            response = self.lab_tests_table.query(
                IndexName='code-index',
                KeyConditionExpression=Key('code').eq(code)
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except ClientError:
            return None
    
    def get_tests_by_category(self, category: str, min_price: int = 0, max_price: int = 999999) -> List[Dict[str, Any]]:
        """Get lab tests by category and price range using GSI"""
        try:
            response = self.lab_tests_table.query(
                IndexName='category-price-index',
                KeyConditionExpression=Key('category').eq(category) & Key('price').between(min_price, max_price),
                FilterExpression=Attr('is_active').eq(True)
            )
            return response.get('Items', [])
        except ClientError:
            return []
    
    def create_test(self, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new lab test"""
        test_id = f"test_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'
        
        item = {
            'test_id': test_id,
            'name': test_data['name'],
            'code': test_data['code'],
            'description': test_data.get('description', ''),
            'category': test_data['category'],
            'sub_category': test_data.get('sub_category', ''),
            'sample_type': test_data.get('sample_type', ''),
            'requirements': test_data.get('requirements', ''),
            'procedure': test_data.get('procedure', ''),
            'price': test_data['price'],  # Already in paisa
            'duration_minutes': test_data.get('duration_minutes'),
            'report_delivery_hours': test_data.get('report_delivery_hours'),
            'is_active': test_data.get('is_active', True),
            'is_home_collection_available': test_data.get('is_home_collection_available', False),
            'minimum_age': test_data.get('minimum_age'),
            'maximum_age': test_data.get('maximum_age'),
            'reference_ranges': test_data.get('reference_ranges', ''),
            'units': test_data.get('units', ''),
            'created_at': now,
            'updated_at': now,
            'created_by': test_data.get('created_by', 'admin')
        }
        
        try:
            self.lab_tests_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create lab test: {str(e)}")
    
    def update_test(self, test_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update lab test"""
        try:
            # Get existing test first
            existing_test = self.get_test_by_id(test_id)
            if not existing_test:
                raise Exception("Lab test not found")
            
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat() + 'Z'}
            
            for key, value in updates.items():
                if key not in ['test_id', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value
            
            self.lab_tests_table.update_item(
                Key={'test_id': test_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            # Return updated item
            updated_test = self.get_test_by_id(test_id)
            return updated_test
        except ClientError as e:
            raise Exception(f"Failed to update lab test: {str(e)}")

class ReportService(DynamoDBService):
    """Report management service using DynamoDB"""
    
    def get_user_reports(self, user_id: str, status: str = None) -> List[Dict[str, Any]]:
        """Get reports for a specific user"""
        try:
            if status:
                response = self.reports_table.query(
                    IndexName='user-status-index',
                    KeyConditionExpression=Key('user_id').eq(user_id),
                    FilterExpression=Attr('status').eq(status),
                    ScanIndexForward=False  # Latest first
                )
            else:
                response = self.reports_table.query(
                    IndexName='user-status-index',
                    KeyConditionExpression=Key('user_id').eq(user_id),
                    ScanIndexForward=False  # Latest first
                )
            
            return response.get('Items', [])
        except ClientError:
            return []
    
    def get_report_by_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get report by ID"""
        try:
            response = self.reports_table.get_item(Key={'report_id': report_id})
            return response.get('Item')
        except ClientError:
            return None
    
    def get_report_by_number(self, report_number: str) -> Optional[Dict[str, Any]]:
        """Get report by report number using GSI"""
        try:
            response = self.reports_table.query(
                IndexName='report-number-index',
                KeyConditionExpression=Key('report_number').eq(report_number)
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except ClientError:
            return None
    
    def create_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new report"""
        report_id = f"rpt_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'
        report_number = f"RPT{datetime.utcnow().strftime('%Y%m%d')}{report_id[-6:]}"
        
        item = {
            'report_id': report_id,
            'user_id': report_data['user_id'],
            'lab_test_id': report_data['lab_test_id'],
            'report_number': report_number,
            'status': report_data.get('status', 'pending'),
            'scheduled_at': self._serialize_datetime(report_data.get('scheduled_at')),
            'created_at': now,
            'updated_at': now,
            'notes': report_data.get('notes', ''),
            'priority': report_data.get('priority', 'normal'),
            'payment_status': report_data.get('payment_status', 'pending'),
            'is_verified': report_data.get('is_verified', False),
            'amount_charged': report_data.get('amount_charged', 0)
        }
        
        try:
            self.reports_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create report: {str(e)}")
    
    def update_report(self, report_id: str, updates: Dict[str, Any]) -> bool:
        """Update report data"""
        try:
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat() + 'Z'}
            
            for key, value in updates.items():
                if key not in ['report_id', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value
            
            self.reports_table.update_item(
                Key={'report_id': report_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            return True
        except ClientError:
            return False

class BookingService(DynamoDBService):
    """Booking management service using DynamoDB"""
    
    def get_user_bookings(self, user_id: str, date_from: datetime = None) -> List[Dict[str, Any]]:
        """Get bookings for a specific user"""
        try:
            if date_from:
                response = self.bookings_table.query(
                    IndexName='user-date-index',
                    KeyConditionExpression=Key('user_id').eq(user_id) & Key('appointment_date').gte(date_from.isoformat() + 'Z'),
                    ScanIndexForward=True  # Earliest first
                )
            else:
                response = self.bookings_table.query(
                    IndexName='user-date-index',
                    KeyConditionExpression=Key('user_id').eq(user_id),
                    ScanIndexForward=True  # Earliest first
                )
            
            return response.get('Items', [])
        except ClientError:
            return []
    
    def get_booking_by_id(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """Get booking by ID"""
        try:
            response = self.bookings_table.get_item(Key={'booking_id': booking_id})
            return response.get('Item')
        except ClientError:
            return None
    
    def get_booking_by_reference(self, booking_reference: str) -> Optional[Dict[str, Any]]:
        """Get booking by reference using GSI"""
        try:
            response = self.bookings_table.query(
                IndexName='reference-index',
                KeyConditionExpression=Key('booking_reference').eq(booking_reference)
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except ClientError:
            return None
    
    def create_booking(self, booking_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new booking"""
        booking_id = f"book_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Generate booking reference
        import secrets
        import string
        chars = string.ascii_uppercase + string.digits
        booking_reference = 'BK' + ''.join(secrets.choice(chars) for _ in range(6))
        
        item = {
            'booking_id': booking_id,
            'user_id': booking_data['user_id'],
            'test_id': booking_data['test_id'],
            'booking_reference': booking_reference,
            'patient_name': booking_data['patient_name'],
            'patient_age': booking_data['patient_age'],
            'patient_gender': booking_data['patient_gender'],
            'appointment_date': self._serialize_datetime(booking_data['appointment_date']),
            'home_collection': booking_data.get('home_collection', False),
            'address': booking_data.get('address', ''),
            'phone_number': booking_data['phone_number'],
            'special_instructions': booking_data.get('special_instructions', ''),
            'status': booking_data.get('status', 'pending'),
            'created_at': now,
            'updated_at': now
        }
        
        try:
            self.bookings_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create booking: {str(e)}")
    
    def update_booking(self, booking_id: str, updates: Dict[str, Any]) -> bool:
        """Update booking data"""
        try:
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat() + 'Z'}
            
            for key, value in updates.items():
                if key not in ['booking_id', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value
            
            self.bookings_table.update_item(
                Key={'booking_id': booking_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            return True
        except ClientError:
            return False

# Service instances for easy import
user_service = UserService()
lab_test_service = LabTestService()
report_service = ReportService()
booking_service = BookingService()