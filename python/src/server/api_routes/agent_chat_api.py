"""
Agent Chat API - Polling-based chat with SSE proxy to AI agents
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/agent-chat", tags=["agent-chat"])

# Simple in-memory session storage
sessions: dict[str, dict] = {}


# Request/Response models
class CreateSessionRequest(BaseModel):
    project_id: str | None = None
    agent_type: str = "rag"


class ChatMessage(BaseModel):
    id: str
    content: str
    sender: str
    timestamp: datetime
    agent_type: str | None = None


# REST Endpoints (minimal for frontend compatibility)
@router.post("/sessions")
async def create_session(request: CreateSessionRequest):
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": session_id,
        "session_id": session_id,  # Frontend expects this
        "project_id": request.project_id,
        "agent_type": request.agent_type,
        "messages": [],
        "created_at": datetime.now().isoformat(),
    }
    logger.info(f"Created chat session {session_id} with agent_type: {request.agent_type}")
    return {"session_id": session_id}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session information."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, after: str = None):
    """Get messages for a session (for polling)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = sessions[session_id].get("messages", [])

    # If 'after' parameter is provided, only return messages after that ID
    if after:
        after_index = -1
        for i, msg in enumerate(messages):
            if msg["id"] == after:
                after_index = i
                break

        if after_index >= 0:
            # Return messages after the specified ID
            return messages[after_index + 1:]
        else:
            # If the 'after' ID is not found, return all messages
            return messages

    return messages


@router.post("/sessions/{session_id}/send")
async def send_message(session_id: str, request: dict):
    """REST endpoint for sending messages."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Store user message
    user_msg = {
        "id": str(uuid.uuid4()),
        "content": request.get("message", ""),
        "sender": "user",
        "timestamp": datetime.now().isoformat(),
    }
    sessions[session_id]["messages"].append(user_msg)

    # Try to send message to agents service
    try:
        import httpx
        import os

        # Get the agent type from session
        session = sessions[session_id]
        agent_type = session.get("agent_type", "spanish_tutor")

        # Prepare request for agents service
        agents_request = {
            "agent_type": agent_type,
            "prompt": request.get("message", ""),
            "context": request.get("context", {
                "student_level": "intermediate",
                "conversation_mode": "casual"
            })
        }

        # Send to agents service
        agents_port = os.getenv("ARCHON_AGENTS_PORT", "8052")
        agents_host = os.getenv("ARCHON_AGENTS_HOST", "archon-agents")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://{agents_host}:{agents_port}/agents/run",
                json=agents_request,
                timeout=8.0,
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("result"):
                    # Store agent response
                    agent_msg = {
                        "id": str(uuid.uuid4()),
                        "content": result["result"]["output"],
                        "sender": "agent",
                        "timestamp": datetime.now().isoformat(),
                        "agent_type": agent_type,
                    }
                    sessions[session_id]["messages"].append(agent_msg)
                    logger.info(f"Agent {agent_type} responded successfully")
                else:
                    logger.error(f"Agent response failed: {result}")
                    # Store a helpful fallback message so the UI shows feedback
                    fallback_msg = {
                        "id": str(uuid.uuid4()),
                        "content": "Agent service responded without a result. Please try again later.",
                        "sender": "agent",
                        "timestamp": datetime.now().isoformat(),
                        "agent_type": agent_type,
                    }
                    sessions[session_id]["messages"].append(fallback_msg)
            else:
                logger.error(f"Agents service returned {response.status_code}")
                fallback_msg = {
                    "id": str(uuid.uuid4()),
                    "content": "Agent service is unavailable (HTTP error). Please check the Agents service.",
                    "sender": "agent",
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": agent_type,
                }
                sessions[session_id]["messages"].append(fallback_msg)

    except Exception as e:
        logger.error(f"Failed to communicate with agents service: {e}")
        # Append a fallback agent message so the UI shows immediate feedback
        fallback_msg = {
            "id": str(uuid.uuid4()),
            "content": "Agent service is currently unreachable. If you're running locally, ensure the Agents service is running and reachable.",
            "sender": "agent",
            "timestamp": datetime.now().isoformat(),
            "agent_type": sessions[session_id].get("agent_type", "unknown"),
        }
        sessions[session_id]["messages"].append(fallback_msg)

    return {"status": "sent"}
