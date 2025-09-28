#!/usr/bin/env python3
"""
Test script for DynamoDB-based Booking Copilot functionality

This demonstrates how to:
1. Seed data via API endpoints
2. Test the copilot with DynamoDB backend
3. Validate the complete flow works

Usage examples:
python test_dynamodb_copilot.py --seed-only    # Just seed data
python test_dynamodb_copilot.py --test-only    # Just test (assuming data exists)
python test_dynamodb_copilot.py                # Seed and test
"""

import requests
import json
import sys
import argparse
from typing import Dict, Any


class DynamoDBCopilotTester:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url

    def seed_via_api(self) -> bool:
        """Seed data using the admin API endpoints"""
        print("🔄 Seeding data via API...")

        try:
            # Use the quick thyroid data seed endpoint
            seed_url = f"{self.base_url}/admin/seed/thyroid-data"
            response = requests.post(seed_url)

            if response.status_code == 200:
                result = response.json()
                print("✅ Thyroid data seeded successfully!")
                print(f"   - Lab tests: {len(result['lab_tests']['created_tests'])} tests, {len(result['lab_tests']['created_panels'])} panels")
                print(f"   - AI rules: {len(result['ai_rules']['created_rules'])} rules")
                return True
            else:
                print(f"❌ Seeding failed: {response.status_code} - {response.text}")
                return False

        except requests.exceptions.ConnectionError:
            print("❌ Failed to connect to API. Make sure the server is running on localhost:8000")
            return False
        except Exception as e:
            print(f"❌ Seeding error: {e}")
            return False

    def test_admin_endpoints(self) -> bool:
        """Test the admin endpoints"""
        print("\n🔍 Testing admin endpoints...")

        try:
            # Test get lab tests
            tests_url = f"{self.base_url}/admin/lab-tests"
            response = requests.get(tests_url)
            if response.status_code == 200:
                tests = response.json()
                print(f"✅ Retrieved {tests['count']} lab tests")
            else:
                print(f"❌ Failed to get lab tests: {response.status_code}")
                return False

            # Test get AI rules
            rules_url = f"{self.base_url}/admin/ai-rules"
            response = requests.get(rules_url)
            if response.status_code == 200:
                rules = response.json()
                print(f"✅ Retrieved {rules['count']} AI rules")
            else:
                print(f"❌ Failed to get AI rules: {response.status_code}")
                return False

            return True

        except Exception as e:
            print(f"❌ Admin endpoints test error: {e}")
            return False

    def test_copilot_conversation(self) -> bool:
        """Test the booking copilot conversation flow"""
        print("\n🤖 Testing Booking Copilot conversation...")

        conversation_steps = [
            "Hi, I've been feeling very tired and fatigued lately",
            "I've also been gaining weight and feeling cold",
            "Tell me more about the TFT Basic panel",
            "Yes, I'd like to book this test",
            "John Doe",      # Name
            "35",            # Age
            "Male",          # Gender
            "9876543210",    # Phone
            "2024-02-15",    # Date
            "Lab",           # Location preference
            "110001",        # Pincode
            "10:00",         # Time slot
            "Yes, confirm the booking"  # Final confirmation
        ]

        session_id = None

        try:
            for i, user_input in enumerate(conversation_steps, 1):
                print(f"\n👤 Step {i}: {user_input}")

                chat_url = f"{self.base_url}/booking-copilot/chat"
                payload = {
                    "message": user_input,
                    "session_id": session_id
                }

                response = requests.post(chat_url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    session_id = result["session_id"]  # Maintain session
                    print(f"🤖 Agent ({result['state']}): {result['response'][:200]}...")

                    # Check for booking confirmation
                    if "Booking Confirmed" in result["response"]:
                        print("🎉 Booking completed successfully!")
                        return True

                else:
                    print(f"❌ Chat failed at step {i}: {response.status_code} - {response.text}")
                    return False

            print("⚠️  Conversation completed but no booking confirmation found")
            return False

        except Exception as e:
            print(f"❌ Copilot conversation error: {e}")
            return False

    def test_direct_api_endpoints(self) -> bool:
        """Test the direct API endpoints for search functionality"""
        print("\n🔬 Testing direct API endpoints...")

        try:
            # Test symptom search
            search_url = f"{self.base_url}/booking-copilot/panels/search"
            params = {
                "symptoms": "fatigue,weight gain,cold",
                "age": 35,
                "gender": "male"
            }

            response = requests.get(search_url, params=params)
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Symptom search found {result['total_found']} recommendations")

                if result["recommendations"]:
                    panel = result["recommendations"][0]
                    panel_id = panel["panel_id"]
                    print(f"   Top recommendation: {panel['panel_name']} (Score: {panel['score']:.2f})")

                    # Test panel details
                    panel_url = f"{self.base_url}/booking-copilot/panels/{panel_id}"
                    response = requests.get(panel_url)
                    if response.status_code == 200:
                        panel_details = response.json()
                        print(f"✅ Panel details retrieved: {panel_details['name']}")
                    else:
                        print(f"❌ Failed to get panel details: {response.status_code}")
                        return False

                    # Test slot search
                    slots_url = f"{self.base_url}/booking-copilot/slots/search"
                    slot_params = {
                        "panel_id": panel_id,
                        "date": "2024-02-15",
                        "pincode": "110001",
                        "home_collection": False
                    }

                    response = requests.get(slots_url, params=slot_params)
                    if response.status_code == 200:
                        slots_result = response.json()
                        print(f"✅ Found {slots_result['total_slots']} available slots")
                    else:
                        print(f"❌ Failed to search slots: {response.status_code}")
                        return False

                else:
                    print("⚠️  No recommendations found for symptoms")

            else:
                print(f"❌ Symptom search failed: {response.status_code} - {response.text}")
                return False

            return True

        except Exception as e:
            print(f"❌ Direct API test error: {e}")
            return False

    def test_session_management(self) -> bool:
        """Test session management features"""
        print("\n🔗 Testing session management...")

        try:
            # Start a conversation to get a session
            chat_url = f"{self.base_url}/booking-copilot/chat"
            payload = {"message": "Hi, I feel tired"}

            response = requests.post(chat_url, json=payload)
            if response.status_code != 200:
                print(f"❌ Failed to start session: {response.status_code}")
                return False

            session_id = response.json()["session_id"]
            print(f"✅ Session created: {session_id[:8]}...")

            # Test session status
            status_url = f"{self.base_url}/booking-copilot/session/{session_id}/status"
            response = requests.get(status_url)
            if response.status_code == 200:
                status = response.json()
                print(f"✅ Session status: {status['state']}")
            else:
                print(f"❌ Failed to get session status: {response.status_code}")
                return False

            # Test session history
            history_url = f"{self.base_url}/booking-copilot/session/{session_id}/history"
            response = requests.get(history_url)
            if response.status_code == 200:
                history = response.json()
                print(f"✅ Session history: {history['total_steps']} steps")
            else:
                print(f"❌ Failed to get session history: {response.status_code}")
                return False

            return True

        except Exception as e:
            print(f"❌ Session management test error: {e}")
            return False

    def run_all_tests(self, seed_only: bool = False, test_only: bool = False) -> bool:
        """Run all tests"""
        print("🚀 DynamoDB Booking Copilot Test Suite")
        print("=" * 60)

        success = True

        if not test_only:
            # Seed data
            if not self.seed_via_api():
                return False

        if not seed_only:
            # Test admin endpoints
            if not self.test_admin_endpoints():
                success = False

            # Test direct API endpoints
            if not self.test_direct_api_endpoints():
                success = False

            # Test session management
            if not self.test_session_management():
                success = False

            # Test full conversation (might take longer)
            print("\n" + "=" * 60)
            print("🎯 RUNNING FULL CONVERSATION TEST")
            print("=" * 60)

            if not self.test_copilot_conversation():
                success = False

        print("\n" + "=" * 60)
        if success:
            print("🎉 ALL TESTS PASSED!")
            print("✅ DynamoDB-based Booking Copilot is working correctly")
        else:
            print("❌ SOME TESTS FAILED!")
            print("⚠️  Check the output above for details")

        print("=" * 60)
        return success


def main():
    parser = argparse.ArgumentParser(description="Test DynamoDB Booking Copilot")
    parser.add_argument("--seed-only", action="store_true", help="Only seed data, don't run tests")
    parser.add_argument("--test-only", action="store_true", help="Only run tests, don't seed data")
    parser.add_argument("--url", default="http://localhost:8000/api/v1", help="API base URL")

    args = parser.parse_args()

    tester = DynamoDBCopilotTester(base_url=args.url)

    try:
        success = tester.run_all_tests(seed_only=args.seed_only, test_only=args.test_only)
        return 0 if success else 1

    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)