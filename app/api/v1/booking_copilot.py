"""
Booking Copilot API endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from app.services.booking_copilot.agent import BookingCopilotAgent, AgentState
from app.services.dynamodb_service import agent_audit_service


router = APIRouter()


# Pydantic models for request/response
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    state: str
    context: Dict[str, Any]
    timestamp: str


class SessionStatus(BaseModel):
    session_id: str
    state: str
    context: Dict[str, Any]
    created_at: str
    last_activity: str


@router.post("/chat", response_model=ChatResponse)
async def chat_with_copilot(
    chat_message: ChatMessage
):
    """
    Main chat endpoint for the booking copilot

    This endpoint processes user messages and returns AI responses
    for test recommendations and booking assistance.
    """
    try:
        # Initialize or continue agent session
        agent = BookingCopilotAgent(
            session_id=chat_message.session_id
        )

        # Add safety disclaimer on first interaction
        if not chat_message.session_id or agent.state == AgentState.COLLECTING_SYMPTOMS:
            safety_prefix = """
**🏥 VitaCheck Labs - Test Booking Assistant**

I'm here to help you find and book appropriate lab tests based on your symptoms.

**Important Disclaimers:**
- I provide test recommendations for screening purposes only
- I cannot diagnose medical conditions
- Always consult healthcare providers for medical advice
- Test results should be interpreted by qualified professionals

Let's get started! What symptoms or health concerns would you like to explore today?

---

"""
            if not chat_message.message.strip():
                return ChatResponse(
                    response=safety_prefix,
                    session_id=agent.session_id,
                    state=agent.state.value,
                    context=agent.context,
                    timestamp=datetime.now().isoformat()
                )
        else:
            safety_prefix = ""

        # Process the user message
        response = agent.process_message(chat_message.message)

        # Add safety prefix if this is the first message
        full_response = safety_prefix + response if safety_prefix else response

        return ChatResponse(
            response=full_response,
            session_id=agent.session_id,
            state=agent.state.value,
            context=agent.context,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        # Log error and return user-friendly message
        raise HTTPException(
            status_code=500,
            detail="I apologize, but I'm experiencing technical difficulties. Please try again in a moment."
        )


@router.get("/session/{session_id}/status", response_model=SessionStatus)
async def get_session_status(
    session_id: str
):
    """
    Get the current status and context of a chat session
    """
    try:
        # Get session audit logs to reconstruct state
        audit_logs = agent_audit_service.get_session_audit(session_id, limit=10)

        if not audit_logs:
            raise HTTPException(status_code=404, detail="Session not found")

        latest_log = audit_logs[0]

        # Try to reconstruct context from audit logs
        context = latest_log.get('conversation_context') or {}

        return SessionStatus(
            session_id=session_id,
            state=latest_log.get('agent_state', {}).get("current_state", "collecting_symptoms") if latest_log.get('agent_state') else "collecting_symptoms",
            context=context,
            created_at=audit_logs[-1]['created_at'],
            last_activity=latest_log['created_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error retrieving session status")


@router.get("/session/{session_id}/history")
async def get_session_history(
    session_id: str,
    limit: int = Query(default=50, le=100)
):
    """
    Get conversation history for a session
    """
    try:
        audit_logs = agent_audit_service.get_session_audit(session_id, limit=limit)

        if not audit_logs:
            raise HTTPException(status_code=404, detail="Session not found")

        history = []
        for log in reversed(audit_logs):  # Reverse to get chronological order
            if log.get('input_data') or log.get('output_data'):
                history.append({
                    "step_number": log['step_number'],
                    "step_type": log['step_type'],
                    "step_name": log.get('step_name', ''),
                    "input_data": log.get('input_data'),
                    "output_data": log.get('output_data'),
                    "timestamp": log['created_at'],
                    "success": log.get('is_success', True)
                })

        return {
            "session_id": session_id,
            "history": history,
            "total_steps": len(audit_logs)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error retrieving session history")


@router.delete("/session/{session_id}")
async def end_session(
    session_id: str
):
    """
    End a chat session and clean up resources
    """
    try:
        # Mark session as completed in audit logs
        completion_audit_data = {
            'session_id': session_id,
            'step_number': 999,  # High number to indicate session end
            'step_type': 'completed',
            'step_name': "Session ended by user",
            'metadata': {"session_ended": True, "ended_at": datetime.now().isoformat()}
        }

        agent_audit_service.create_audit_entry(completion_audit_data)

        return {"message": "Session ended successfully", "session_id": session_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error ending session")


@router.get("/panels/search")
async def search_panels(
    symptoms: str = Query(..., description="Comma-separated list of symptoms"),
    age: Optional[int] = Query(None, description="Patient age"),
    gender: Optional[str] = Query(None, description="Patient gender")
):
    """
    Direct API to search for test panels based on symptoms
    (Can be used by other services or for testing)
    """
    try:
        from app.services.booking_copilot.tools_dynamodb import BookingCopilotTools

        tools = BookingCopilotTools()
        symptom_list = [s.strip() for s in symptoms.split(",")]

        recommendations = tools.symptom_rules(
            symptoms=symptom_list,
            age=age,
            gender=gender
        )

        return {
            "symptoms": symptom_list,
            "recommendations": recommendations,
            "total_found": len(recommendations)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error searching panels")


@router.get("/panels/{panel_id}")
async def get_panel_details(
    panel_id: int
):
    """
    Get detailed information about a specific test panel
    """
    try:
        from app.services.booking_copilot.tools_dynamodb import BookingCopilotTools

        tools = BookingCopilotTools()
        panel = tools.get_panel(panel_id)

        if not panel:
            raise HTTPException(status_code=404, detail="Panel not found")

        return panel

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error retrieving panel details")


@router.get("/slots/search")
async def search_slots(
    panel_id: int = Query(..., description="Panel ID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    pincode: str = Query(..., description="Location pincode"),
    home_collection: bool = Query(False, description="Whether home collection is requested")
):
    """
    Search for available appointment slots
    """
    try:
        from app.services.booking_copilot.tools_dynamodb import BookingCopilotTools

        tools = BookingCopilotTools()
        slots = tools.slot_search(
            panel_id=panel_id,
            pincode=pincode,
            date=date,
            home=home_collection
        )

        return {
            "panel_id": panel_id,
            "date": date,
            "pincode": pincode,
            "home_collection": home_collection,
            "available_slots": slots,
            "total_slots": len(slots)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Error searching slots")


@router.get("/health")
async def health_check():
    """Health check endpoint for the booking copilot service"""
    return {
        "service": "booking_copilot",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "symptom_analysis",
            "test_recommendations",
            "appointment_booking",
            "reminder_scheduling",
            "conversation_tracking"
        ]
    }