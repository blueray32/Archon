"""
MCP API endpoints for Archon

Provides status and configuration endpoints for the MCP service.
The MCP container is managed by docker-compose, not by this API.
"""

import os
from typing import Any

import docker
from docker.errors import NotFound
from fastapi import APIRouter, HTTPException
import httpx

# Import unified logging
from ..config.logfire_config import api_logger, safe_set_attribute, safe_span

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


def get_container_status() -> dict[str, Any]:
    """Get simple MCP container status without Docker management."""
    docker_client = None
    try:
        docker_client = docker.from_env()
        container = docker_client.containers.get("archon-mcp")

        # Get container status
        container_status = container.status

        # Map Docker statuses to simple statuses
        if container_status == "running":
            status = "running"
            # Try to get uptime from container info
            try:
                from datetime import datetime
                started_at = container.attrs["State"]["StartedAt"]
                started_time = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime = int((datetime.now(started_time.tzinfo) - started_time).total_seconds())
            except Exception:
                uptime = None
        else:
            status = "stopped"
            uptime = None

        return {
            "status": status,
            "uptime": uptime,
            "logs": [],  # No log streaming anymore
            "container_status": container_status
        }

    except NotFound:
        return {
            "status": "not_found",
            "uptime": None,
            "logs": [],
            "container_status": "not_found",
            "message": "MCP container not found. Run: docker compose up -d archon-mcp"
        }
    except Exception as e:
        api_logger.error("Failed to get container status", exc_info=True)
        return {
            "status": "error",
            "uptime": None,
            "logs": [],
            "container_status": "error",
            "error": str(e)
        }
    finally:
        if docker_client is not None:
            try:
                docker_client.close()
            except Exception:
                pass


@router.get("/status")
async def get_status():
    """Get MCP server status."""
    with safe_span("api_mcp_status") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/status")
        safe_set_attribute(span, "method", "GET")

        try:
            status = get_container_status()
            api_logger.debug(f"MCP server status checked - status={status.get('status')}")
            safe_set_attribute(span, "status", status.get("status"))
            safe_set_attribute(span, "uptime", status.get("uptime"))
            return status
        except Exception as e:
            api_logger.error(f"MCP server status API failed - error={str(e)}")
            safe_set_attribute(span, "error", str(e))
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_mcp_config():
    """Get MCP server configuration."""
    with safe_span("api_get_mcp_config") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/config")
        safe_set_attribute(span, "method", "GET")

        try:
            api_logger.info("Getting MCP server configuration")

            # Get actual MCP port from environment or use default
            mcp_port = int(os.getenv("ARCHON_MCP_PORT", "8051"))

            # Configuration for streamable-http mode with actual port
            config = {
                "host": "localhost",
                "port": mcp_port,
                "transport": "streamable-http",
            }

            # Get only model choice from database (simplified)
            try:
                from ..services.credential_service import credential_service

                model_choice = await credential_service.get_credential(
                    "MODEL_CHOICE", "gpt-4o-mini"
                )
                config["model_choice"] = model_choice
            except Exception:
                # Fallback to default model
                config["model_choice"] = "gpt-4o-mini"

            api_logger.info("MCP configuration (streamable-http mode)")
            safe_set_attribute(span, "host", config["host"])
            safe_set_attribute(span, "port", config["port"])
            safe_set_attribute(span, "transport", "streamable-http")
            safe_set_attribute(span, "model_choice", config.get("model_choice", "gpt-4o-mini"))

            return config
        except Exception as e:
            api_logger.error("Failed to get MCP configuration", exc_info=True)
            safe_set_attribute(span, "error", str(e))
            raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/clients")
async def get_mcp_clients():
    """Get connected MCP clients with type detection."""
    with safe_span("api_mcp_clients") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/clients")
        safe_set_attribute(span, "method", "GET")

        try:
            # TODO: Implement real client detection in the future
            # For now, return empty array as expected by frontend
            api_logger.debug("Getting MCP clients - returning empty array")

            return {
                "clients": [],
                "total": 0
            }
        except Exception as e:
            api_logger.error(f"Failed to get MCP clients - error={str(e)}")
            safe_set_attribute(span, "error", str(e))
            return {
                "clients": [],
                "total": 0,
                "error": str(e)
            }


@router.get("/sessions")
async def get_mcp_sessions():
    """Get MCP session information."""
    with safe_span("api_mcp_sessions") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/sessions")
        safe_set_attribute(span, "method", "GET")

        try:
            # Basic session info for now
            status = get_container_status()

            session_info = {
                "active_sessions": 0,  # TODO: Implement real session tracking
                "session_timeout": 3600,  # 1 hour default
            }

            # Add uptime if server is running
            if status.get("status") == "running" and status.get("uptime"):
                session_info["server_uptime_seconds"] = status["uptime"]

            api_logger.debug(f"MCP session info - sessions={session_info.get('active_sessions')}")
            safe_set_attribute(span, "active_sessions", session_info.get("active_sessions"))

            return session_info
        except Exception as e:
            api_logger.error(f"Failed to get MCP sessions - error={str(e)}")
            safe_set_attribute(span, "error", str(e))
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def mcp_health():
    """Health check for MCP API - used by bug report service and tests."""
    with safe_span("api_mcp_health") as span:
        safe_set_attribute(span, "endpoint", "/api/mcp/health")
        safe_set_attribute(span, "method", "GET")

        # Simple health check - no logging to reduce noise
        result = {"status": "healthy", "service": "mcp"}
        safe_set_attribute(span, "status", "healthy")

    return result


@router.post("/session/init")
async def init_mcp_session():
    """Initialize an MCP session and return the session ID.

    Useful for debugging clients that report "No valid session ID provided".
    """
    with safe_span("api_mcp_session_init") as span:
        try:
            mcp_port = int(os.getenv("ARCHON_MCP_PORT", "8051"))
            candidates = [f"http://archon-mcp:{mcp_port}", f"http://localhost:{mcp_port}"]

            payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "archon-api", "version": "1.0.0"},
                },
                "id": "init",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                session_id = None
                mcp_url = None
                last_error = None
                for base in candidates:
                    try:
                        resp = await client.post(f"{base}/mcp", json=payload, headers={"Accept": "application/json, text/event-stream"})
                        resp.raise_for_status()
                        session_id = resp.headers.get("mcp-session-id")
                        mcp_url = base
                        break
                    except Exception as e:
                        last_error = e
                        continue

            if not session_id:
                raise HTTPException(status_code=502, detail="MCP did not return a session ID")

            return {"session_id": session_id, "mcp_url": mcp_url}

        except HTTPException:
            raise
        except Exception as e:
            api_logger.error("Failed to initialize MCP session", exc_info=True)
            raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/session/info")
async def get_session_info():
    """Call MCP session_info tool and return its response."""
    with safe_span("api_mcp_session_info") as span:
        try:
            mcp_port = int(os.getenv("ARCHON_MCP_PORT", "8051"))
            candidates = [f"http://archon-mcp:{mcp_port}", f"http://localhost:{mcp_port}"]

            # Step 1: initialize to get a session id
            init_body = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "clientInfo": {"name": "archon-api", "version": "1.0.0"},
                },
                "id": "init",
            }

            call_body = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": "session_info", "arguments": {}},
                "id": "call",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                last_error = None
                for base in candidates:
                    try:
                        init_resp = await client.post(
                            f"{base}/mcp",
                            json=init_body,
                            headers={"Accept": "application/json, text/event-stream"},
                        )
                        init_resp.raise_for_status()
                        session_id = init_resp.headers.get("mcp-session-id")

                        headers = {"Accept": "application/json, text/event-stream"}
                        if session_id:
                            headers["mcp-session-id"] = session_id

                        resp = await client.post(f"{base}/mcp", json=call_body, headers=headers)
                        resp.raise_for_status()
                        data = resp.json() if resp.headers.get("content-type","" ).startswith("application/json") else resp.text
                        return data
                    except Exception as e:
                        last_error = e
                        continue

            raise HTTPException(status_code=502, detail={"error": str(last_error) if last_error else "All connection attempts failed"})

            return data
        except Exception as e:
            api_logger.error("Failed to call MCP session_info", exc_info=True)
            raise HTTPException(status_code=500, detail={"error": str(e)})
