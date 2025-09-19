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

        # Prepare common request body
        base_request = {
            "prompt": request.get("message", ""),
            "context": request.get(
                "context",
                {"student_level": "intermediate", "conversation_mode": "casual"},
            ),
        }

        # If pydantic_ai isn't available on the agents service, fall back to rag
        types_to_try = [agent_type]
        if agent_type == "pydantic_ai":
            types_to_try.append("rag")

        agents_port = os.getenv("ARCHON_AGENTS_PORT", "8052")
        agents_host = os.getenv("ARCHON_AGENTS_HOST", "archon-agents")
        async with httpx.AsyncClient() as client:
            success = False
            final_error_text = None
            for idx, t in enumerate(types_to_try):
                try:
                    agents_request = dict(base_request)
                    agents_request["agent_type"] = t
                    response = await client.post(
                        f"http://{agents_host}:{agents_port}/agents/run",
                        json=agents_request,
                        timeout=8.0,
                    )

                    # Handle 400 Unknown agent type responses
                    if response.status_code == 400:
                        body_text = ""
                        try:
                            body_text = response.text
                        except Exception:
                            pass
                        if "Unknown agent type" in body_text and t == "pydantic_ai":
                            logger.info("Agents service unknown 'pydantic_ai'; trying fallback next")
                            continue  # try next type

                    if response.status_code == 200:
                        result = response.json()
                        # Some services return 200 with success=false; detect and retry if unknown
                        if not result.get("success"):
                            err_text = str(result.get("error") or "")
                            if "Unknown agent type" in err_text and t == "pydantic_ai":
                                logger.info("Agents returned 200 with Unknown agent type error; trying fallback next")
                                continue  # try next type
                            final_error_text = err_text or f"Unknown error (type={t})"
                            continue

                        # Success path
                        output = result.get("result")
                        if isinstance(output, dict):
                            content = output.get("output")
                        else:
                            content = None
                        if not content:
                            try:
                                import json
                                content = json.dumps(output, ensure_ascii=False)
                            except Exception:
                                content = str(output)

                        agent_msg = {
                            "id": str(uuid.uuid4()),
                            "content": content,
                            "sender": "agent",
                            "timestamp": datetime.now().isoformat(),
                            "agent_type": t,
                        }
                        sessions[session_id]["messages"].append(agent_msg)
                        logger.info(f"Agent {t} responded successfully")
                        success = True
                        break
                    else:
                        final_error_text = f"HTTP {response.status_code}"
                        # Try next type if available
                        continue
                except Exception as e:
                    final_error_text = str(e)
                    continue

            if not success:
                # Provide a helpful fallback message
                fallback_msg = {
                    "id": str(uuid.uuid4()),
                    "content": f"Agent error: {final_error_text or 'Service unavailable'}",
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
@router.get("/status")
async def agent_chat_status():
    """Lightweight status check for the Agents service used by the UI."""
    try:
        import httpx
        import os
        agents_port = os.getenv("ARCHON_AGENTS_PORT", "8052")
        agents_host = os.getenv("ARCHON_AGENTS_HOST", "archon-agents")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{agents_host}:{agents_port}/health", timeout=5.0)
            ok = resp.status_code == 200
            return {"online": ok, "status": resp.status_code, "agents_host": agents_host, "agents_port": agents_port}
    except Exception as e:
        logger.error(f"Agents status check failed: {e}")
        return {"online": False, "error": str(e)}
