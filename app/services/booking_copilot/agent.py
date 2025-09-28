"""
Booking Copilot Agent Core
Handles the conversational AI logic for test recommendations and booking
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json
import uuid
from enum import Enum

from app.services.booking_copilot.tools_dynamodb import BookingCopilotToolsDynamoDB


class AgentState(Enum):
    """Agent conversation states"""
    COLLECTING_SYMPTOMS = "collecting_symptoms"
    PRESENTING_RECOMMENDATIONS = "presenting_recommendations"
    EXPLAINING_PANEL = "explaining_panel"
    COLLECTING_PATIENT_INFO = "collecting_patient_info"
    FINDING_SLOTS = "finding_slots"
    CONFIRMING_BOOKING = "confirming_booking"
    BOOKING_COMPLETE = "booking_complete"
    ERROR = "error"


class BookingCopilotAgent:
    """Main agent class for the booking copilot"""

    def __init__(self, db=None, session_id: Optional[str] = None):
        self.db = db  # Keep for compatibility, but DynamoDB tools don't need it
        self.tools = BookingCopilotToolsDynamoDB()
        self.session_id = session_id or str(uuid.uuid4())
        self.state = AgentState.COLLECTING_SYMPTOMS
        self.context = {
            "symptoms": [],
            "patient_info": {},
            "selected_panel": None,
            "selected_slot": None,
            "booking_details": None,
            "conversation_history": []
        }

    def get_planner_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """Generate planner prompt based on current state and context"""

        base_prompt = """You are a helpful medical test booking assistant. Your role is to:
1. Understand patient symptoms (non-diagnostic language only)
2. Recommend appropriate test panels based on symptoms
3. Provide clear information about tests, pricing, and preparation
4. Help book appointments with proper confirmation
5. Always require explicit confirmation before booking

IMPORTANT SAFETY GUIDELINES:
- Use non-diagnostic language only
- Don't diagnose medical conditions
- Recommend consulting healthcare providers
- Always show disclaimers for recommendations
- Require confirmation before booking anything

Current conversation state: {state}
User input: "{user_input}"

Context:
- Symptoms collected: {symptoms}
- Patient info: {patient_info}
- Selected panel: {selected_panel}
- Selected slot: {selected_slot}
"""

        state_specific_prompts = {
            AgentState.COLLECTING_SYMPTOMS: """
Your current task: Collect symptoms from the user and understand what they're experiencing.

Guidelines:
- Ask open-ended questions about symptoms
- Use non-diagnostic language
- Collect relevant details (duration, severity, etc.)
- Don't suggest medical conditions
- Once you have sufficient symptoms, recommend test panels

Example responses:
- "I understand you're experiencing fatigue. Can you tell me more about when this started and how it's affecting you?"
- "Are there any other symptoms you've noticed along with the fatigue?"
- "Based on what you've shared, I can recommend some test panels that might help assess these symptoms."
""",

            AgentState.PRESENTING_RECOMMENDATIONS: """
Your current task: Present test panel recommendations based on collected symptoms.

Guidelines:
- Present 2-3 top recommendations with clear rationale
- Include pricing, timing, and what each panel tests
- Use disclaimers about multiple potential causes
- Ask which panel they'd like to learn more about
- Don't use diagnostic language

Example response format:
"Based on your symptoms, here are some test panels that might be helpful:

1. **Thyroid Function Test (TFT) - Basic** - ₹500
   - Tests: TSH, Free T4
   - Rationale: Fatigue is commonly associated with thyroid function
   - Report delivery: 24 hours

*Disclaimer: These symptoms can have multiple causes. This testing is for screening purposes only.*

Which panel would you like to learn more about?"
""",

            AgentState.EXPLAINING_PANEL: """
Your current task: Provide detailed information about the selected test panel.

Guidelines:
- Explain what the panel tests and why it's relevant
- Detail preparation requirements
- Show pricing and timing clearly
- Mention home collection availability
- Ask if they'd like to proceed with booking

Example response:
"The TFT Basic panel tests thyroid hormone levels (TSH and Free T4) which can help assess thyroid function related to your fatigue symptoms.

**Preparation:** No fasting required. Avoid biotin supplements 72 hours before.
**Sample:** Blood test (single draw)
**Price:** ₹500
**Report:** Available in 24 hours
**Collection:** Available at lab or home (₹100 extra)

Would you like to proceed with booking this test?"
""",

            AgentState.COLLECTING_PATIENT_INFO: """
Your current task: Collect patient information for booking.

Required information:
- Patient name
- Age
- Gender
- Contact phone number
- Preferred date
- Location preference (lab vs home)
- Address (if home collection)

Guidelines:
- Ask for one piece of information at a time
- Validate information as you collect it
- Be clear about what information is needed and why
""",

            AgentState.FINDING_SLOTS: """
Your current task: Find and present available appointment slots.

Guidelines:
- Show available time slots clearly
- Mention any additional costs (home collection)
- Present options in an easy-to-choose format
- Ask for their preferred slot selection
""",

            AgentState.CONFIRMING_BOOKING: """
Your current task: Confirm all booking details before finalizing.

CRITICAL: Always show complete booking summary and get explicit confirmation.

Guidelines:
- Display all booking details clearly
- Show total cost including any extras
- Require explicit "yes" or "confirm" before booking
- Provide booking reference after confirmation
- Schedule reminders automatically
"""
        }

        state_prompt = state_specific_prompts.get(self.state, "")

        return base_prompt.format(
            state=self.state.value,
            user_input=user_input,
            symptoms=context.get("symptoms", []),
            patient_info=context.get("patient_info", {}),
            selected_panel=context.get("selected_panel"),
            selected_slot=context.get("selected_slot")
        ) + state_prompt

    def get_reflector_prompt(self, action_result: Dict[str, Any], user_input: str) -> str:
        """Generate reflector prompt to assess action results and plan next steps"""

        return f"""
You just took an action and got this result: {json.dumps(action_result, indent=2)}

Original user input: "{user_input}"
Current state: {self.state.value}

Reflection questions:
1. Was the action successful? Did it achieve the intended goal?
2. What information do we now have that we didn't before?
3. What should be the next step in the conversation?
4. Should we change the conversation state?
5. What should we communicate back to the user?

Based on this reflection, provide:
1. A clear response to the user about what happened
2. The next appropriate question or action
3. Whether to change the conversation state
4. Any safety disclaimers that should be included

Keep responses conversational, helpful, and always use non-diagnostic language.
Ensure the user feels informed and in control of the booking process.
"""

    def plan_action(self, user_input: str) -> Dict[str, Any]:
        """
        Plan the next action based on user input and current state

        Returns:
            Dict with planned action details
        """
        user_input_lower = user_input.lower().strip()

        # Log planning step
        self.tools.audit(
            step="Planning agent response",
            metadata={
                "user_input": user_input,
                "current_state": self.state.value,
                "context": self.context,
                "contains_symptoms": any(symptom in user_input_lower for symptom in ["tired", "fatigue", "weight", "hair", "heart", "cold", "hot", "nausea", "jaundice", "yellow", "dark urine", "bone pain", "weakness", "bruising"])
            },
            session_id=self.session_id
        )

        if self.state == AgentState.COLLECTING_SYMPTOMS:
            return self._plan_symptom_collection(user_input, user_input_lower)

        elif self.state == AgentState.PRESENTING_RECOMMENDATIONS:
            return self._plan_recommendation_presentation(user_input, user_input_lower)

        elif self.state == AgentState.EXPLAINING_PANEL:
            return self._plan_panel_explanation(user_input, user_input_lower)

        elif self.state == AgentState.COLLECTING_PATIENT_INFO:
            return self._plan_patient_info_collection(user_input, user_input_lower)

        elif self.state == AgentState.FINDING_SLOTS:
            return self._plan_slot_finding(user_input, user_input_lower)

        elif self.state == AgentState.CONFIRMING_BOOKING:
            return self._plan_booking_confirmation(user_input, user_input_lower)

        else:
            return {"action": "error", "message": "Unknown state"}

    def _plan_symptom_collection(self, user_input: str, user_input_lower: str) -> Dict[str, Any]:
        """Plan action for symptom collection state"""

        # Extract symptoms from input
        potential_symptoms = []
        symptom_keywords = [
            # Vitamin D related
            "bone pain", "muscle weakness", "fractures", "osteoporosis", "rickets", "weak bones",
            "brittle bones", "bone aches", "muscle aches", "joint pain", "back pain",
            "chronic fatigue", "depression", "mood swings", "seasonal depression", "low energy",
            "tiredness", "feeling down", "sad mood", "winter blues", "exhaustion", "lethargy",

            # Liver related
            "abdominal pain", "nausea", "vomiting", "loss of appetite", "indigestion",
            "stomach pain", "belly pain", "feeling sick", "digestive problems", "liver pain",
            "jaundice", "yellow eyes", "yellow skin", "dark urine", "pale stools", "clay colored stools",
            "yellowish skin", "golden eyes", "amber urine", "light colored stool",

            # Thyroid related
            "unexplained weight gain", "unexplained weight loss", "weight", "fatigue", "tiredness",
            "metabolism changes", "gaining weight", "losing weight", "slow metabolism", "fast metabolism",
            "heat intolerance", "cold intolerance", "feeling too hot", "feeling too cold",
            "temperature sensitivity", "always cold", "always hot", "cannot tolerate heat", "cannot tolerate cold",
            "heart palpitations", "rapid heartbeat", "racing heart", "irregular heartbeat",
            "chest pounding", "fast heart rate", "heart racing", "tachycardia", "cardiac symptoms",

            # Blood related (CBC)
            "chronic fatigue", "weakness", "shortness of breath", "dizziness", "pale skin",
            "feeling faint", "tired all the time", "no energy", "breathlessness", "lightheaded", "pallor",
            "frequent infections", "recurring colds", "slow healing", "frequent fever", "repeated illness",
            "always getting sick", "poor immunity", "infection prone", "weak immune system",
            "easy bruising", "prolonged bleeding", "nosebleeds", "heavy periods", "bleeding gums",
            "bruise easily", "slow clotting", "excessive bleeding", "menorrhagia", "epistaxis",

            # Legacy keywords
            "tired", "exhausted", "energy", "hair", "heart", "cold", "hot", "sweating",
            "mood", "anxiety", "family history", "thyroid"
        ]

        for keyword in symptom_keywords:
            if keyword in user_input_lower:
                potential_symptoms.append(keyword)

        if potential_symptoms:
            self.context["symptoms"].extend(potential_symptoms)

        # Check if we have enough symptoms to make recommendations
        if len(self.context["symptoms"]) >= 1:
            return {
                "action": "get_recommendations",
                "tool": "symptom_rules",
                "parameters": {
                    "symptoms": self.context["symptoms"]
                }
            }
        else:
            return {
                "action": "ask_more_symptoms",
                "message": "I'd like to understand what you're experiencing. Can you tell me about any symptoms or health concerns that brought you here today?"
            }

    def _plan_recommendation_presentation(self, user_input: str, user_input_lower: str) -> Dict[str, Any]:
        """Plan action for recommendation presentation state"""

        # Check if user is asking about a specific panel or wants to proceed
        if any(word in user_input_lower for word in ["basic", "complete", "thyroid", "tft"]):
            # Try to identify which panel they're asking about
            panel_id = None
            if "basic" in user_input_lower:
                panel_id = self._find_panel_by_code("TFT-BASIC")
            elif "complete" in user_input_lower:
                panel_id = self._find_panel_by_code("TFT-COMPLETE")

            if panel_id:
                self.context["selected_panel"] = panel_id
                return {
                    "action": "explain_panel",
                    "tool": "get_panel",
                    "parameters": {"panel_id": panel_id}
                }

        elif any(word in user_input_lower for word in ["book", "proceed", "yes", "want"]):
            return {
                "action": "ask_panel_selection",
                "message": "Which test panel would you like to book? Please let me know the specific panel you're interested in."
            }

        return {
            "action": "clarify_choice",
            "message": "Which test panel would you like to learn more about, or would you like me to explain the recommendations in more detail?"
        }

    def _plan_panel_explanation(self, user_input: str, user_input_lower: str) -> Dict[str, Any]:
        """Plan action for panel explanation state"""

        if any(word in user_input_lower for word in ["book", "proceed", "yes", "want"]):
            self.state = AgentState.COLLECTING_PATIENT_INFO
            return {
                "action": "start_patient_info",
                "message": "Great! I'll help you book this test. Let me collect some information. What's the patient's full name?"
            }

        elif any(word in user_input_lower for word in ["price", "cost", "how much"]):
            return {
                "action": "show_pricing",
                "tool": "get_price_eta",
                "parameters": {"panel_id": self.context["selected_panel"]}
            }

        elif any(word in user_input_lower for word in ["prep", "preparation", "before"]):
            return {
                "action": "show_preparation",
                "tool": "get_prep",
                "parameters": {"panel_id": self.context["selected_panel"]}
            }

        return {
            "action": "ask_proceed",
            "message": "Would you like to proceed with booking this test, or do you have any other questions about it?"
        }

    def _plan_patient_info_collection(self, user_input: str, user_input_lower: str) -> Dict[str, Any]:
        """Plan action for patient info collection state"""

        # Collect patient information step by step
        if "name" not in self.context["patient_info"]:
            self.context["patient_info"]["name"] = user_input.strip()
            return {
                "action": "ask_age",
                "message": "Thank you. What's the patient's age?"
            }

        elif "age" not in self.context["patient_info"]:
            try:
                age = int(user_input.strip())
                self.context["patient_info"]["age"] = age
                return {
                    "action": "ask_gender",
                    "message": "What's the patient's gender? (Male/Female/Other)"
                }
            except ValueError:
                return {
                    "action": "ask_age_again",
                    "message": "Please provide the age as a number."
                }

        elif "gender" not in self.context["patient_info"]:
            self.context["patient_info"]["gender"] = user_input.strip()
            return {
                "action": "ask_phone",
                "message": "What's the contact phone number?"
            }

        elif "phone" not in self.context["patient_info"]:
            self.context["patient_info"]["phone"] = user_input.strip()
            return {
                "action": "ask_date",
                "message": "What date would you prefer for the test? (Please provide in YYYY-MM-DD format)"
            }

        elif "date" not in self.context["patient_info"]:
            self.context["patient_info"]["date"] = user_input.strip()
            return {
                "action": "ask_location",
                "message": "Would you prefer to visit our lab or have the sample collected at home? (Lab collection is free, home collection has an additional ₹100 charge)"
            }

        elif "location_type" not in self.context["patient_info"]:
            home_collection = any(word in user_input_lower for word in ["home", "house", "collect"])
            self.context["patient_info"]["location_type"] = "home" if home_collection else "lab"

            if home_collection:
                return {
                    "action": "ask_address",
                    "message": "Please provide the full address for home collection."
                }
            else:
                return {
                    "action": "ask_pincode",
                    "message": "What's your pincode so I can find the nearest lab location?"
                }

        else:
            # All info collected, move to slot finding
            if self.context["patient_info"]["location_type"] == "home" and "address" not in self.context["patient_info"]:
                self.context["patient_info"]["address"] = user_input.strip()

            pincode = user_input.strip() if "pincode" not in self.context["patient_info"] else self.context["patient_info"].get("pincode", "110001")
            self.context["patient_info"]["pincode"] = pincode

            self.state = AgentState.FINDING_SLOTS
            return {
                "action": "find_slots",
                "tool": "slot_search",
                "parameters": {
                    "panel_id": self.context["selected_panel"],
                    "pincode": pincode,
                    "date": self.context["patient_info"]["date"],
                    "home": self.context["patient_info"]["location_type"] == "home"
                }
            }

    def _plan_slot_finding(self, user_input: str, user_input_lower: str) -> Dict[str, Any]:
        """Plan action for slot finding state"""

        # User is selecting a time slot
        self.context["selected_slot"] = {"slot_id": user_input.strip(), "time": user_input.strip()}
        self.state = AgentState.CONFIRMING_BOOKING
        return {
            "action": "confirm_booking",
            "message": "Perfect! Let me confirm all the booking details before we finalize."
        }

    def _plan_booking_confirmation(self, user_input: str, user_input_lower: str) -> Dict[str, Any]:
        """Plan action for booking confirmation state"""

        if any(word in user_input_lower for word in ["yes", "confirm", "proceed", "book"]):
            return {
                "action": "create_booking",
                "tool": "book_test",
                "parameters": {
                    "patient": {
                        "name": self.context["patient_info"]["name"],
                        "age": self.context["patient_info"]["age"],
                        "gender": self.context["patient_info"]["gender"]
                    },
                    "panel_id": self.context["selected_panel"],
                    "slot": self.context["selected_slot"],
                    "home": self.context["patient_info"]["location_type"] == "home",
                    "address": self.context["patient_info"].get("address"),
                    "phone": self.context["patient_info"]["phone"],
                    "user_id": 1  # TODO: Get from auth context
                }
            }

        return {
            "action": "ask_confirmation",
            "message": "Please confirm if you'd like to proceed with this booking by saying 'yes' or 'confirm'."
        }

    def _find_panel_by_code(self, code: str) -> Optional[str]:
        """Find panel ID by code using DynamoDB"""
        panel = self.tools.lab_test_service.get_test_by_code(code)
        return panel['test_id'] if panel else None

    def execute_action(self, action_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the planned action"""

        action_type = action_plan["action"]

        # Log the action execution
        self.tools.audit(
            step=f"Executing action: {action_type}",
            metadata={
                "action_plan": action_plan,
                "tool_name": action_plan.get("tool"),
                "tool_parameters": action_plan.get("parameters")
            },
            session_id=self.session_id
        )

        if action_plan.get("tool"):
            # Execute tool function
            tool_name = action_plan["tool"]
            parameters = action_plan.get("parameters", {})

            if hasattr(self.tools, tool_name):
                tool_func = getattr(self.tools, tool_name)
                try:
                    result = tool_func(**parameters)
                    return {"success": True, "result": result, "action": action_type}
                except Exception as e:
                    return {"success": False, "error": str(e), "action": action_type}
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}", "action": action_type}

        else:
            # Direct message action
            return {
                "success": True,
                "message": action_plan.get("message", ""),
                "action": action_type
            }

    def reflect_and_respond(self, action_result: Dict[str, Any], user_input: str) -> str:
        """Reflect on action results and generate user response"""

        if not action_result.get("success", True):
            return f"I apologize, but I encountered an issue: {action_result.get('error', 'Unknown error')}. Let me try to help you in a different way."

        action_type = action_result.get("action", "")

        if action_type == "get_recommendations":
            recommendations = action_result.get("result", [])
            if recommendations:
                self.state = AgentState.PRESENTING_RECOMMENDATIONS
                response = "Based on your symptoms, here are some test panels that might be helpful:\n\n"

                for i, rec in enumerate(recommendations[:3], 1):
                    response += f"{i}. **{rec['panel_name']}** - ₹{rec['price']:.0f}\n"
                    response += f"   - {rec['rationale']}\n"
                    response += f"   - Report delivery: {rec['report_delivery_hours']} hours\n\n"

                response += "*Disclaimer: These symptoms can have multiple causes. This testing is for screening purposes only. Please consult with a healthcare provider for proper medical evaluation.*\n\n"
                response += "Which panel would you like to learn more about?"

                return response
            else:
                return "I don't have specific test recommendations for those symptoms at the moment. Would you like me to connect you with our support team for personalized guidance?"

        elif action_type == "explain_panel":
            panel = action_result.get("result")
            if panel:
                self.state = AgentState.EXPLAINING_PANEL
                response = f"**{panel['name']}**\n\n"
                response += f"**Description:** {panel['description']}\n\n"
                response += f"**What's included:**\n"

                if panel.get("included_tests"):
                    for test in panel["included_tests"]:
                        response += f"- {test['name']} ({test['code']})\n"

                response += f"\n**Details:**\n"
                response += f"- **Price:** {panel['price_formatted']}\n"
                response += f"- **Sample type:** {panel['sample_type']}\n"
                response += f"- **Report delivery:** {panel['report_delivery_hours']} hours\n"
                response += f"- **Home collection:** {'Available (₹100 extra)' if panel['is_home_collection_available'] else 'Not available'}\n\n"

                if panel['requirements']:
                    response += f"**Preparation:** {panel['requirements']}\n\n"

                response += "Would you like to proceed with booking this test?"
                return response

        elif action_type == "find_slots":
            slots = action_result.get("result", [])
            if slots:
                self.state = AgentState.FINDING_SLOTS
                location_type = self.context["patient_info"]["location_type"]
                response = f"Here are the available time slots for {location_type} collection on {self.context['patient_info']['date']}:\n\n"

                for slot in slots:
                    extra_cost = f" (+₹{slot['cost_extra']})" if slot['cost_extra'] > 0 else ""
                    response += f"• {slot['time']} at {slot['location']}{extra_cost}\n"

                response += "\nPlease let me know which time slot you prefer."
                return response
            else:
                return "I'm sorry, no slots are available for that date. Would you like to try a different date?"

        elif action_type == "create_booking":
            booking = action_result.get("result")
            if booking:
                self.state = AgentState.BOOKING_COMPLETE
                self.context["booking_details"] = booking

                # Schedule reminders
                reminder_result = self.tools.schedule_reminder(booking, booking.get("user_id", 1))

                response = f"🎉 **Booking Confirmed!**\n\n"
                response += f"**Booking Reference:** {booking['booking_reference']}\n"
                response += f"**Patient:** {booking['patient_name']}\n"
                response += f"**Test:** {booking['test_name']}\n"
                response += f"**Date & Time:** {booking['appointment_date']}\n"
                response += f"**Location:** {booking['location_type'].title()} Collection\n"
                response += f"**Total Cost:** ₹{booking['total_cost']:.0f}\n\n"

                if booking['location_type'] == 'home':
                    response += f"**Address:** {booking['address']}\n\n"

                response += "**What's next:**\n"
                response += "- You'll receive SMS reminders about preparation and appointment\n"
                response += "- Report will be available in 24-48 hours after sample collection\n"
                response += "- Contact us if you need to reschedule\n\n"

                response += "*Disclaimer: This test is for screening purposes. Please consult your healthcare provider for medical interpretation of results.*"

                return response

        # Default responses for other actions
        return action_result.get("message", "I'm here to help you with test bookings. What would you like to do?")

    def process_message(self, user_input: str) -> str:
        """Main method to process user message and return response"""

        try:
            # Add to conversation history
            self.context["conversation_history"].append({
                "user": user_input,
                "timestamp": datetime.now().isoformat()
            })

            # Plan action based on current state and input
            action_plan = self.plan_action(user_input)

            # Execute the planned action
            action_result = self.execute_action(action_plan)

            # Reflect on results and generate response
            response = self.reflect_and_respond(action_result, user_input)

            # Add response to conversation history
            self.context["conversation_history"].append({
                "agent": response,
                "timestamp": datetime.now().isoformat(),
                "state": self.state.value
            })

            # DynamoDB operations are auto-committed, no need for manual commit

            return response

        except Exception as e:
            # DynamoDB doesn't need rollback
            error_msg = f"I apologize, but I encountered an unexpected error. Please try again or contact support if the issue persists."

            # Log error
            self.tools.audit(
                step="Error in message processing",
                metadata={
                    "error": str(e),
                    "user_input": user_input,
                    "state": self.state.value
                },
                session_id=self.session_id
            )

            return error_msg