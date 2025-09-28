"""
DynamoDB-based tool functions for the booking copilot agent
Replaces the SQLAlchemy-based tools with DynamoDB operations
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
import json
import random
from decimal import Decimal

from app.services.dynamodb_service import (
    lab_test_service,
    ai_rules_service,
    booking_service,
    agent_audit_service,
    reminders_service
)


class BookingCopilotToolsDynamoDB:
    """DynamoDB-based tool functions for the booking copilot"""

    def __init__(self):
        self.lab_test_service = lab_test_service
        self.ai_rules_service = ai_rules_service
        self.booking_service = booking_service
        self.agent_audit_service = agent_audit_service
        self.reminders_service = reminders_service

    def symptom_rules(self, symptoms: List[str], age: Optional[int] = None, gender: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get ranked test panels based on symptoms using AI rules from DynamoDB

        Args:
            symptoms: List of symptoms to match against
            age: Optional patient age for age-specific rules
            gender: Optional patient gender for gender-specific rules

        Returns:
            List of recommended panels with scores and rationale
        """
        if not symptoms:
            return []

        try:
            # Get matching rules from DynamoDB
            matching_rules = self.ai_rules_service.get_rules_for_symptoms(symptoms, age, gender)

            recommendations = []
            for rule in matching_rules:
                # Get panel details by code
                panel = self.lab_test_service.get_test_by_code(rule['panel_code'])
                if panel and panel.get('is_active'):
                    recommendation = {
                        "panel_id": panel['test_id'],
                        "panel_name": panel['name'],
                        "panel_code": panel['code'],
                        "score": rule.get('calculated_score', rule.get('weight', 0)),
                        "rule_name": rule['name'],
                        "rationale": rule.get('rationale', ''),
                        "requires_confirmation": rule.get('requires_confirmation', True),
                        "disclaimers": rule.get('disclaimers', []),
                        "price": float(panel['price']),
                        "duration_minutes": panel.get('duration_minutes', 30),
                        "report_delivery_hours": panel.get('report_delivery_hours', 24),
                        "matched_symptoms": [s for s in symptoms if self._symptom_matches_rule(s, rule)]
                    }
                    recommendations.append(recommendation)

            return recommendations[:5]  # Return top 5 recommendations

        except Exception as e:
            print(f"Error in symptom_rules: {e}")
            return []

    def _symptom_matches_rule(self, symptom: str, rule: Dict[str, Any]) -> bool:
        """Check if a symptom matches a rule"""
        symptom_lower = symptom.lower().strip()
        rule_symptoms = [s.lower().strip() for s in rule.get('symptoms', [])]
        rule_synonyms = [s.lower().strip() for s in rule.get('synonyms', [])]

        return (symptom_lower in rule_symptoms or
                symptom_lower in rule_synonyms or
                any(symptom_lower in rs or rs in symptom_lower for rs in rule_symptoms + rule_synonyms))

    def get_panel(self, panel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific test panel from DynamoDB

        Args:
            panel_id: The panel ID to retrieve

        Returns:
            Panel information or None if not found
        """
        try:
            panel = self.lab_test_service.get_test_by_id(panel_id)
            if not panel or not panel.get('is_active'):
                return None

            result = {
                "id": panel['test_id'],
                "name": panel['name'],
                "code": panel['code'],
                "description": panel.get('description', ''),
                "type": panel.get('type', 'test'),
                "category": panel.get('category', ''),
                "sub_category": panel.get('sub_category', ''),
                "price": float(panel['price']),
                "price_formatted": f"₹{float(panel['price']):.2f}",
                "duration_minutes": panel.get('duration_minutes', 30),
                "report_delivery_hours": panel.get('report_delivery_hours', 24),
                "sample_type": panel.get('sample_type', ''),
                "is_home_collection_available": panel.get('is_home_collection_available', False),
                "requirements": panel.get('requirements', ''),
                "procedure": panel.get('procedure', '')
            }

            # If it's a panel, get included tests
            if panel.get('type') == 'panel' and panel.get('tests_included'):
                included_tests = []
                for test_id in panel['tests_included']:
                    test = self.lab_test_service.get_test_by_id(test_id)
                    if test:
                        included_tests.append({
                            "id": test['test_id'],
                            "name": test['name'],
                            "code": test['code'],
                            "description": test.get('description', ''),
                            "units": test.get('units', '')
                        })
                    else:
                        # Try by code if ID doesn't work
                        test = self.lab_test_service.get_test_by_code(test_id)
                        if test:
                            included_tests.append({
                                "id": test['test_id'],
                                "name": test['name'],
                                "code": test['code'],
                                "description": test.get('description', ''),
                                "units": test.get('units', '')
                            })

                result["included_tests"] = included_tests

            return result

        except Exception as e:
            print(f"Error in get_panel: {e}")
            return None

    def get_price_eta(self, panel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get pricing and ETA information for a test panel from DynamoDB

        Args:
            panel_id: The panel ID

        Returns:
            Price and timing information
        """
        try:
            panel = self.lab_test_service.get_test_by_id(panel_id)
            if not panel or not panel.get('is_active'):
                return None

            # Calculate total completion time
            test_duration = panel.get('duration_minutes', 30)
            report_hours = panel.get('report_delivery_hours', 24)
            total_completion = test_duration + (report_hours * 60)

            return {
                "panel_id": panel['test_id'],
                "panel_name": panel['name'],
                "price": float(panel['price']),
                "price_formatted": f"₹{float(panel['price']):.2f}",
                "test_duration_minutes": test_duration,
                "report_delivery_hours": report_hours,
                "total_completion_minutes": total_completion,
                "estimated_completion": f"{total_completion // 60} hours {total_completion % 60} minutes",
                "currency": "INR"
            }

        except Exception as e:
            print(f"Error in get_price_eta: {e}")
            return None

    def get_prep(self, panel_id: str) -> Optional[Dict[str, Any]]:
        """
        Get preparation instructions for a test panel from DynamoDB

        Args:
            panel_id: The panel ID

        Returns:
            Preparation instructions and requirements
        """
        try:
            panel = self.lab_test_service.get_test_by_id(panel_id)
            if not panel or not panel.get('is_active'):
                return None

            requirements = panel.get('requirements', 'No special preparation required.')

            return {
                "panel_id": panel['test_id'],
                "panel_name": panel['name'],
                "requirements": requirements,
                "procedure": panel.get('procedure', 'Standard blood collection procedure.'),
                "sample_type": panel.get('sample_type', 'Blood'),
                "fasting_required": "fasting" in requirements.lower(),
                "special_instructions": self._extract_special_instructions(requirements)
            }

        except Exception as e:
            print(f"Error in get_prep: {e}")
            return None

    def _extract_special_instructions(self, requirements: Optional[str]) -> List[str]:
        """Extract special instructions from requirements text"""
        if not requirements:
            return []

        instructions = []
        req_lower = requirements.lower()

        if "fasting" in req_lower:
            instructions.append("Fasting required - avoid food and drinks (except water) for recommended period")
        if "biotin" in req_lower:
            instructions.append("Avoid biotin supplements 72 hours before test")
        if "medication" in req_lower:
            instructions.append("Inform lab about current medications")
        if "morning" in req_lower:
            instructions.append("Best collected in the morning")

        return instructions

    def slot_search(self, panel_id: str, pincode: str, date: str, home: bool = False) -> List[Dict[str, Any]]:
        """
        Search for available time slots (Mock implementation with DynamoDB validation)

        Args:
            panel_id: The panel ID
            pincode: Patient's pincode for location-based search
            date: Preferred date in YYYY-MM-DD format
            home: Whether home collection is requested

        Returns:
            List of available slots
        """
        try:
            # Validate panel exists and supports the collection type
            panel = self.lab_test_service.get_test_by_id(panel_id)
            if not panel or not panel.get('is_active'):
                return []

            if home and not panel.get('is_home_collection_available'):
                return []

            # Parse the requested date
            try:
                requested_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                return []

            # Generate mock slots for demo (same logic as before)
            slots = []

            # Lab collection slots (more available)
            if not home:
                lab_times = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]
                for time_str in lab_times:
                    slot_datetime = datetime.combine(requested_date, datetime.strptime(time_str, "%H:%M").time())
                    slot_datetime = slot_datetime.replace(tzinfo=timezone.utc)

                    slots.append({
                        "slot_id": f"LAB_{pincode}_{date}_{time_str}",
                        "type": "lab",
                        "date": date,
                        "time": time_str,
                        "datetime": slot_datetime.isoformat(),
                        "location": f"VitaCheck Lab - {pincode}",
                        "address": f"Main Branch, {pincode} Area",
                        "available": random.choice([True, True, True, False]),  # 75% availability
                        "cost_extra": 0
                    })

            # Home collection slots (limited availability)
            else:
                home_times = ["08:00", "09:00", "10:00", "15:00", "16:00", "17:00"]
                for time_str in home_times:
                    slot_datetime = datetime.combine(requested_date, datetime.strptime(time_str, "%H:%M").time())
                    slot_datetime = slot_datetime.replace(tzinfo=timezone.utc)

                    slots.append({
                        "slot_id": f"HOME_{pincode}_{date}_{time_str}",
                        "type": "home",
                        "date": date,
                        "time": time_str,
                        "datetime": slot_datetime.isoformat(),
                        "location": "Home Collection",
                        "address": "Patient's home address",
                        "available": random.choice([True, True, False]),  # 66% availability
                        "cost_extra": 100  # Extra charge for home collection
                    })

            # Filter only available slots and sort by time
            available_slots = [slot for slot in slots if slot["available"]]
            return sorted(available_slots, key=lambda x: x["time"])

        except Exception as e:
            print(f"Error in slot_search: {e}")
            return []

    def book_test(self, patient: Dict[str, Any], panel_id: str, slot: Dict[str, Any],
                  home: bool, address: Optional[str], phone: str, user_id: str) -> Dict[str, Any]:
        """
        Book a test appointment using DynamoDB

        Args:
            patient: Patient information dict with name, age, gender
            panel_id: The test panel ID
            slot: Selected time slot
            home: Whether it's home collection
            address: Patient address (required if home=True)
            phone: Contact phone number
            user_id: User making the booking

        Returns:
            Booking confirmation details
        """
        try:
            # Validate panel exists
            panel = self.lab_test_service.get_test_by_id(panel_id)
            if not panel or not panel.get('is_active'):
                raise ValueError(f"Panel with ID {panel_id} not found or inactive")

            # Validate home collection
            if home and not panel.get('is_home_collection_available'):
                raise ValueError(f"Home collection not available for {panel['name']}")

            if home and not address:
                raise ValueError("Address is required for home collection")

            # Parse appointment datetime
            appointment_datetime = datetime.fromisoformat(slot["datetime"].replace('Z', '+00:00'))

            # Create booking using DynamoDB service
            booking_data = {
                'user_id': user_id,
                'test_id': panel_id,
                'patient_name': patient["name"],
                'patient_age': patient["age"],
                'patient_gender': patient["gender"],
                'appointment_date': appointment_datetime,
                'home_collection': home,
                'address': address if home else slot.get("address"),
                'phone_number': phone,
                'status': 'pending'
            }

            booking = self.booking_service.create_booking(booking_data)

            return {
                "booking_id": booking['booking_id'],
                "booking_reference": booking['booking_reference'],
                "status": booking['status'],
                "patient_name": booking['patient_name'],
                "test_name": panel['name'],
                "appointment_date": appointment_datetime.isoformat(),
                "location_type": "home" if home else "lab",
                "address": booking['address'],
                "phone": booking['phone_number'],
                "total_cost": float(panel['price']) + (slot.get("cost_extra", 0) if home else 0),
                "created_at": booking['created_at']
            }

        except Exception as e:
            print(f"Error in book_test: {e}")
            raise

    def schedule_reminder(self, booking: Dict[str, Any], user_id: str) -> List[Dict[str, Any]]:
        """
        Schedule reminders for a booking using DynamoDB

        Args:
            booking: Booking information dict
            user_id: User ID for the reminders

        Returns:
            List of scheduled reminders
        """
        try:
            # Parse booking date for reminder scheduling
            booking_date = datetime.fromisoformat(booking["appointment_date"].replace('Z', '+00:00'))

            reminders = []

            # Schedule preparation reminder (48 hours before)
            prep_time = booking_date - timedelta(hours=48)
            prep_reminder_data = {
                'booking_id': booking["booking_id"],
                'user_id': user_id,
                'type': 'preparation',
                'channel': 'sms',
                'scheduled_at': prep_time,
                'title': f'Test Preparation - {booking["test_name"]}',
                'message': f'Hi {booking["patient_name"]}, your test is scheduled for tomorrow. Please follow preparation instructions.',
                'recipient_contact': booking["phone"],
                'template_data': {
                    'patient_name': booking["patient_name"],
                    'test_name': booking["test_name"],
                    'appointment_date': booking["appointment_date"],
                    'booking_reference': booking["booking_reference"]
                }
            }

            prep_reminder = self.reminders_service.create_reminder(prep_reminder_data)
            reminders.append({
                "reminder_id": prep_reminder['reminder_id'],
                "type": prep_reminder['type'],
                "scheduled_at": prep_reminder['scheduled_at'],
                "channel": prep_reminder['channel'],
                "title": prep_reminder['title']
            })

            # Schedule appointment reminder (24 hours before)
            appt_time = booking_date - timedelta(hours=24)
            appt_reminder_data = {
                'booking_id': booking["booking_id"],
                'user_id': user_id,
                'type': 'appointment',
                'channel': 'sms',
                'scheduled_at': appt_time,
                'title': f'Appointment Reminder - {booking["test_name"]}',
                'message': f'Hi {booking["patient_name"]}, reminder about your appointment tomorrow.',
                'recipient_contact': booking["phone"],
                'template_data': {
                    'patient_name': booking["patient_name"],
                    'test_name': booking["test_name"],
                    'appointment_date': booking["appointment_date"],
                    'booking_reference': booking["booking_reference"]
                }
            }

            appt_reminder = self.reminders_service.create_reminder(appt_reminder_data)
            reminders.append({
                "reminder_id": appt_reminder['reminder_id'],
                "type": appt_reminder['type'],
                "scheduled_at": appt_reminder['scheduled_at'],
                "channel": appt_reminder['channel'],
                "title": appt_reminder['title']
            })

            return reminders

        except Exception as e:
            print(f"Error in schedule_reminder: {e}")
            return []

    def audit(self, step: str, metadata: Dict[str, Any], session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create an audit log entry for agent step using DynamoDB

        Args:
            step: Step name/description
            metadata: Additional metadata for the step
            session_id: Agent session ID
            user_id: Optional user ID

        Returns:
            Audit entry confirmation
        """
        try:
            # Determine step type based on step name
            step_type_map = {
                'input': 'input',
                'planning': 'planning',
                'reflection': 'reflection',
                'confirmation': 'confirmation',
                'booking': 'booking',
                'error': 'error',
                'completed': 'completed'
            }

            step_type = 'tool_call'  # default
            for key, value in step_type_map.items():
                if key in step.lower():
                    step_type = value
                    break

            # Get next step number for this session
            existing_audits = self.agent_audit_service.get_session_audit(session_id)
            step_number = len(existing_audits) + 1

            # Create audit entry
            audit_data = {
                'session_id': session_id,
                'step_number': step_number,
                'user_id': user_id or '',
                'step_type': step_type,
                'step_name': step,
                'metadata': metadata,
                'tool_name': metadata.get('tool_name'),
                'tool_parameters': metadata.get('tool_parameters'),
                'tool_result': metadata.get('tool_result'),
                'contains_phi': metadata.get('contains_phi', False),
                'contains_symptoms': metadata.get('contains_symptoms', False)
            }

            audit_entry = self.agent_audit_service.create_audit_entry(audit_data)

            return {
                "audit_id": audit_entry['audit_id'],
                "session_id": session_id,
                "step_number": step_number,
                "step_type": step_type,
                "created_at": audit_entry['created_at']
            }

        except Exception as e:
            print(f"Error in audit: {e}")
            return {
                "audit_id": None,
                "session_id": session_id,
                "step_number": 0,
                "step_type": "error",
                "created_at": datetime.now().isoformat(),
                "error": str(e)
            }