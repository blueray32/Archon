import logging
import os

import httpx
from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)

router = APIRouter()

OPENAI_API_BASE_DEFAULT = "https://api.openai.com"
CHATKIT_SESSION_PATH_DEFAULT = "/v1/chatkits/sessions"


@router.post("/api/chatkit/session")
async def create_chatkit_session() -> dict:
    """Proxy ChatKit session creation to OpenAI."""
    api_key = os.getenv("OPENAI_API_KEY")
    workflow_id = os.getenv("CHATKIT_WORKFLOW_ID")
    api_base = os.getenv("OPENAI_API_BASE", OPENAI_API_BASE_DEFAULT)
    session_path = os.getenv("CHATKIT_SESSION_PATH", CHATKIT_SESSION_PATH_DEFAULT)

    if not api_key:
        logger.error("CHATKIT_SESSION_ENV_MISSING: OPENAI_API_KEY")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ChatKit env not configured: missing OPENAI_API_KEY",
        )

    if not workflow_id:
        logger.error("CHATKIT_SESSION_ENV_MISSING: CHATKIT_WORKFLOW_ID")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ChatKit env not configured: missing CHATKIT_WORKFLOW_ID",
        )

    url = f"{api_base}{session_path}"
    payload = {"workflow_id": workflow_id}
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.error(
            "CHATKIT_SESSION_REQUEST_FAILED: url=%s error=%s",
            url,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"ChatKit session error: {exc}",
        ) from exc

    if response.status_code >= 300:
        logger.error(
            "CHATKIT_SESSION_REMOTE_ERROR: status=%s body=%s",
            response.status_code,
            response.text,
        )
        raise HTTPException(
            status_code=response.status_code,
            detail=f"ChatKit session proxy failed: {response.text}",
        )

    try:
        return response.json()
    except ValueError as exc:
        logger.error(
            "CHATKIT_SESSION_INVALID_JSON: body=%s", response.text, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ChatKit session error: invalid JSON response",
        ) from exc
