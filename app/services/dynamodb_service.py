"""
DynamoDB service layer to replace SQLAlchemy ORM
Provides CRUD operations for all entities using DynamoDB
"""

import boto3
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal
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
        self.report_explanations_table = self.dynamodb.Table('vitachecklabs-report-explanations')
        self.ai_rules_table = self.dynamodb.Table('vitachecklabs-ai-rules')
        self.agent_audit_table = self.dynamodb.Table('vitachecklabs-agent-audit')
        self.reminders_table = self.dynamodb.Table('vitachecklabs-reminders')
    
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
            'type': test_data.get('type', 'test'),  # 'test' or 'panel'
            'tests_included': test_data.get('tests_included', []),  # For panels
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

    def get_panels(self, is_active: bool = True) -> List[Dict[str, Any]]:
        """Get all test panels"""
        try:
            if is_active:
                response = self.lab_tests_table.scan(
                    FilterExpression=Attr('type').eq('panel') & Attr('is_active').eq(True)
                )
            else:
                response = self.lab_tests_table.scan(
                    FilterExpression=Attr('type').eq('panel')
                )
            return response.get('Items', [])
        except ClientError:
            return []

    def get_individual_tests(self, is_active: bool = True) -> List[Dict[str, Any]]:
        """Get all individual tests (non-panels)"""
        try:
            if is_active:
                response = self.lab_tests_table.scan(
                    FilterExpression=Attr('type').eq('test') & Attr('is_active').eq(True)
                )
            else:
                response = self.lab_tests_table.scan(
                    FilterExpression=Attr('type').eq('test')
                )
            return response.get('Items', [])
        except ClientError:
            return []

    def get_panel_with_included_tests(self, panel_id: str) -> Optional[Dict[str, Any]]:
        """Get panel with details of included tests"""
        panel = self.get_test_by_id(panel_id)
        if not panel or panel.get('type') != 'panel':
            return None

        # Get included test details
        included_test_ids = panel.get('tests_included', [])
        included_tests = []

        for test_id in included_test_ids:
            test = self.get_test_by_id(test_id)
            if test:
                included_tests.append(test)

        panel['included_test_details'] = included_tests
        return panel

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
            # Try GSI query first
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
        except ClientError as e:
            # Fallback to scan with filter if GSI doesn't exist
            try:
                # For debugging: print what we're filtering for
                print(f"GSI query failed for user_id: {user_id}, falling back to scan. Error: {e}")

                filter_expression = Attr('user_id').eq(user_id)
                if date_from:
                    filter_expression = filter_expression & Attr('appointment_date').gte(date_from.isoformat() + 'Z')

                response = self.bookings_table.scan(FilterExpression=filter_expression)
                items = response.get('Items', [])

                # Debug: print how many items matched the filter
                print(f"Scan found {len(items)} bookings for user_id: {user_id}")

                return items
            except ClientError as e2:
                print(f"Scan also failed: {e2}")
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


class ReportExplanationService(DynamoDBService):
    """Report explanation management service using DynamoDB"""

    def create_explanation(self, explanation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new report explanation"""
        explanation_id = f"exp_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'

        item = {
            'explanation_id': explanation_id,
            'report_id': str(explanation_data['report_id']),
            'user_id': explanation_data['user_id'],
            'processing_status': explanation_data.get('processing_status', 'pending'),
            'patient_summary': explanation_data.get('patient_summary', ''),
            'clinician_summary': explanation_data.get('clinician_summary', ''),
            'abnormal_values': explanation_data.get('abnormal_values', []),
            'extracted_data': explanation_data.get('extracted_data', {}),
            'ai_model_used': explanation_data.get('ai_model_used', 'gpt-4'),
            'processing_time_seconds': explanation_data.get('processing_time_seconds', 0),
            'error_message': explanation_data.get('error_message', ''),
            'created_at': now,
            'updated_at': now
        }

        try:
            self.report_explanations_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create explanation: {str(e)}")

    def get_explanation_by_id(self, explanation_id: str) -> Optional[Dict[str, Any]]:
        """Get explanation by ID"""
        try:
            response = self.report_explanations_table.get_item(Key={'explanation_id': explanation_id})
            return response.get('Item')
        except ClientError:
            return None

    def get_explanation_by_report_id(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Get explanation by report ID using GSI"""
        try:
            response = self.report_explanations_table.query(
                IndexName='report-id-index',
                KeyConditionExpression=Key('report_id').eq(str(report_id))
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except ClientError:
            return None

    def get_explanations_by_user(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get explanations by user ID using GSI"""
        try:
            response = self.report_explanations_table.query(
                IndexName='user-id-index',
                KeyConditionExpression=Key('user_id').eq(user_id),
                Limit=limit,
                ScanIndexForward=False  # Latest first
            )
            return response.get('Items', [])
        except ClientError:
            return []

    def update_explanation(self, explanation_id: str, updates: Dict[str, Any]) -> bool:
        """Update explanation data"""
        try:
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat() + 'Z'}

            for key, value in updates.items():
                if key not in ['explanation_id', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value

            self.report_explanations_table.update_item(
                Key={'explanation_id': explanation_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            return True
        except ClientError:
            return False

    def delete_explanation(self, explanation_id: str) -> bool:
        """Delete explanation"""
        try:
            self.report_explanations_table.delete_item(Key={'explanation_id': explanation_id})
            return True
        except ClientError:
            return False

    def get_all_explanations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all explanations (admin only)"""
        try:
            response = self.report_explanations_table.scan(Limit=limit)
            return response.get('Items', [])
        except ClientError:
            return []


class AIRulesService(DynamoDBService):
    """AI Rules management service using DynamoDB"""

    def get_active_rules(self) -> List[Dict[str, Any]]:
        """Get all active AI rules"""
        try:
            response = self.ai_rules_table.query(
                IndexName='ActiveRulesIndex',
                KeyConditionExpression=Key('is_active').eq('true')
            )
            return response.get('Items', [])
        except ClientError:
            # Fallback to scan if GSI doesn't exist
            try:
                response = self.ai_rules_table.scan(
                    FilterExpression=Attr('is_active').eq('true')
                )
                return response.get('Items', [])
            except ClientError:
                return []

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get AI rule by ID"""
        try:
            response = self.ai_rules_table.get_item(Key={'rule_id': rule_id})
            return response.get('Item')
        except ClientError:
            return None

    def get_rules_for_symptoms(self, symptoms: List[str], age: int = None, gender: str = None) -> List[Dict[str, Any]]:
        """Get AI rules that match given symptoms"""
        try:
            all_rules = self.get_active_rules()
            matching_rules = []

            for rule in all_rules:
                if self._rule_matches_symptoms(rule, symptoms):
                    if self._rule_applicable_for_patient(rule, age, gender):
                        score = self._calculate_rule_score(rule, symptoms, age, gender)
                        rule['calculated_score'] = score
                        matching_rules.append(rule)

            # Sort by calculated score descending
            return sorted(matching_rules, key=lambda x: x.get('calculated_score', 0), reverse=True)
        except Exception:
            return []

    def _rule_matches_symptoms(self, rule: Dict[str, Any], user_symptoms: List[str]) -> bool:
        """Check if rule matches given symptoms"""
        if not user_symptoms:
            return False

        user_symptoms_lower = [s.lower().strip() for s in user_symptoms]
        rule_symptoms = [s.lower().strip() for s in rule.get('symptoms', [])]
        rule_synonyms = [s.lower().strip() for s in rule.get('synonyms', [])]

        # Check for direct matches
        for symptom in user_symptoms_lower:
            if symptom in rule_symptoms or symptom in rule_synonyms:
                return True

        # Check for partial matches (contains)
        for symptom in user_symptoms_lower:
            for rule_symptom in rule_symptoms + rule_synonyms:
                if symptom in rule_symptom or rule_symptom in symptom:
                    return True

        return False

    def _rule_applicable_for_patient(self, rule: Dict[str, Any], age: int = None, gender: str = None) -> bool:
        """Check if rule is applicable for patient demographics"""
        # Check age restrictions
        if age is not None:
            if rule.get('age_min') and age < rule['age_min']:
                return False
            if rule.get('age_max') and age > rule['age_max']:
                return False

        # Check gender restrictions
        if gender is not None and rule.get('gender_specific'):
            if rule['gender_specific'].lower() != gender.lower():
                return False

        return True

    def _calculate_rule_score(self, rule: Dict[str, Any], user_symptoms: List[str], age: int = None, gender: str = None) -> float:
        """Calculate recommendation score for this rule"""
        base_score = float(rule.get('weight', 0))

        # Bonus for multiple symptom matches
        matches = 0
        user_symptoms_lower = [s.lower().strip() for s in user_symptoms]
        rule_symptoms = [s.lower().strip() for s in rule.get('symptoms', [])]
        rule_synonyms = [s.lower().strip() for s in rule.get('synonyms', [])]

        for symptom in user_symptoms_lower:
            if symptom in rule_symptoms or symptom in rule_synonyms:
                matches += 1

        # Increase score for multiple matches (up to 20% bonus)
        if matches > 1:
            base_score += min(0.2, (matches - 1) * 0.05)

        return min(1.0, base_score)  # Cap at 1.0

    def create_rule(self, rule_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new AI rule"""
        rule_id = f"rule_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'

        item = {
            'rule_id': rule_id,
            'name': rule_data['name'],
            'description': rule_data.get('description', ''),
            'symptoms': rule_data['symptoms'],
            'synonyms': rule_data.get('synonyms', []),
            'panel_code': rule_data['panel_code'],
            'weight': Decimal(str(rule_data.get('weight', 0.5))),
            'rationale': rule_data.get('rationale', ''),
            'disclaimers': rule_data.get('disclaimers', []),
            'age_min': rule_data.get('age_min'),
            'age_max': rule_data.get('age_max'),
            'gender_specific': rule_data.get('gender_specific'),
            'requires_confirmation': rule_data.get('requires_confirmation', True),
            'is_active': 'true' if rule_data.get('is_active', True) else 'false',
            'created_at': now,
            'updated_at': now,
            'created_by': rule_data.get('created_by', 'admin')
        }

        try:
            self.ai_rules_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create AI rule: {str(e)}")

    def update_rule(self, rule_id: str, updates: Dict[str, Any]) -> bool:
        """Update AI rule"""
        try:
            update_expression = "SET updated_at = :updated_at"
            expression_values = {':updated_at': datetime.utcnow().isoformat() + 'Z'}

            for key, value in updates.items():
                if key not in ['rule_id', 'created_at']:
                    if key == 'is_active':
                        value = 'true' if value else 'false'
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value

            self.ai_rules_table.update_item(
                Key={'rule_id': rule_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            return True
        except ClientError:
            return False


class AgentAuditService(DynamoDBService):
    """Agent audit management service using DynamoDB"""

    def create_audit_entry(self, audit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new audit entry"""
        audit_id = f"audit_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'

        item = {
            'audit_id': audit_id,
            'session_id': audit_data['session_id'],
            'step_number': audit_data['step_number'],
            'user_id': audit_data.get('user_id', ''),
            'step_type': audit_data['step_type'],
            'step_name': audit_data.get('step_name', ''),
            'input_data': audit_data.get('input_data', {}),
            'output_data': audit_data.get('output_data', {}),
            'metadata': audit_data.get('metadata', {}),
            'tool_name': audit_data.get('tool_name', ''),
            'tool_parameters': audit_data.get('tool_parameters', {}),
            'tool_result': audit_data.get('tool_result', {}),
            'started_at': audit_data.get('started_at', now),
            'completed_at': audit_data.get('completed_at'),
            'duration_ms': audit_data.get('duration_ms', 0),
            'is_success': audit_data.get('is_success', True),
            'error_message': audit_data.get('error_message', ''),
            'contains_phi': audit_data.get('contains_phi', False),
            'contains_symptoms': audit_data.get('contains_symptoms', False),
            'created_at': now
        }

        try:
            self.agent_audit_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create audit entry: {str(e)}")

    def get_session_audit(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit entries for a session"""
        try:
            response = self.agent_audit_table.query(
                KeyConditionExpression=Key('session_id').eq(session_id),
                Limit=limit,
                ScanIndexForward=True  # Chronological order
            )
            return response.get('Items', [])
        except ClientError:
            return []

    def get_user_audit(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get audit entries for a user"""
        try:
            response = self.agent_audit_table.query(
                IndexName='UserAuditIndex',
                KeyConditionExpression=Key('user_id').eq(user_id),
                Limit=limit,
                ScanIndexForward=False  # Latest first
            )
            return response.get('Items', [])
        except ClientError:
            return []


class RemindersService(DynamoDBService):
    """Reminders management service using DynamoDB"""

    def create_reminder(self, reminder_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new reminder"""
        reminder_id = f"reminder_{uuid.uuid4()}"
        now = datetime.utcnow().isoformat() + 'Z'

        item = {
            'reminder_id': reminder_id,
            'booking_id': reminder_data['booking_id'],
            'user_id': reminder_data['user_id'],
            'type': reminder_data['type'],
            'channel': reminder_data['channel'],
            'scheduled_at': self._serialize_datetime(reminder_data['scheduled_at']),
            'title': reminder_data['title'],
            'message': reminder_data['message'],
            'template_data': reminder_data.get('template_data', {}),
            'status': reminder_data.get('status', 'scheduled'),
            'recipient_contact': reminder_data['recipient_contact'],
            'delivery_attempts': reminder_data.get('delivery_attempts', 0),
            'max_attempts': reminder_data.get('max_attempts', 3),
            'is_active': reminder_data.get('is_active', True),
            'priority': reminder_data.get('priority', 1),
            'created_at': now,
            'updated_at': now
        }

        try:
            self.reminders_table.put_item(Item=item)
            return item
        except ClientError as e:
            raise Exception(f"Failed to create reminder: {str(e)}")

    def get_pending_reminders(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get reminders that are due to be sent"""
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            response = self.reminders_table.query(
                IndexName='ScheduledRemindersIndex',
                KeyConditionExpression=Key('status').eq('scheduled') & Key('scheduled_at').lte(now),
                Limit=limit
            )
            return response.get('Items', [])
        except ClientError:
            return []

    def get_booking_reminders(self, booking_id: str) -> List[Dict[str, Any]]:
        """Get reminders for a specific booking"""
        try:
            response = self.reminders_table.query(
                IndexName='BookingRemindersIndex',
                KeyConditionExpression=Key('booking_id').eq(booking_id)
            )
            return response.get('Items', [])
        except ClientError:
            return []

    def update_reminder_status(self, reminder_id: str, status: str, **kwargs) -> bool:
        """Update reminder status and other fields"""
        try:
            update_expression = "SET #status = :status, updated_at = :updated_at"
            expression_values = {
                ':status': status,
                ':updated_at': datetime.utcnow().isoformat() + 'Z'
            }
            expression_names = {'#status': 'status'}

            # Handle additional fields
            for key, value in kwargs.items():
                if key not in ['reminder_id', 'created_at']:
                    update_expression += f", {key} = :{key}"
                    expression_values[f":{key}"] = value

            self.reminders_table.update_item(
                Key={'reminder_id': reminder_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names
            )
            return True
        except ClientError:
            return False


# Service instances for easy import
user_service = UserService()
lab_test_service = LabTestService()
report_service = ReportService()
booking_service = BookingService()
report_explanation_service = ReportExplanationService()
ai_rules_service = AIRulesService()
agent_audit_service = AgentAuditService()
reminders_service = RemindersService()