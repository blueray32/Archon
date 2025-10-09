"""
MCP Client for Agents

This lightweight client allows PydanticAI agents to call MCP tools via HTTP.
Agents use this client to access all data operations through the MCP protocol
instead of direct database access or service imports.
"""

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for calling MCP tools via HTTP."""

    def __init__(self, mcp_url: str = None):
        """
        Initialize MCP client.

        Args:
            mcp_url: MCP server URL (defaults to service discovery)
        """
        if mcp_url:
            self.mcp_url = mcp_url
        else:
            # Use service discovery to find MCP server
            try:
                from ..server.config.service_discovery import get_mcp_url

                self.mcp_url = get_mcp_url()
            except ImportError:
                # Fallback for when running in agents container
                import os

                mcp_port = os.getenv("ARCHON_MCP_PORT", "8051")
                if os.getenv("DOCKER_CONTAINER"):
                    self.mcp_url = f"http://archon-mcp:{mcp_port}"
                else:
                    self.mcp_url = f"http://localhost:{mcp_port}"

        self.client = httpx.AsyncClient(timeout=30.0)
        self.session_id = None
        logger.info(f"MCP Client initialized with URL: {self.mcp_url}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def _ensure_session(self):
        """Ensure an MCP session is initialized."""
        if self.session_id is not None:
            return

        try:
            # Initialize session with MCP server
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "archon-agents",
                        "version": "1.0.0"
                    }
                },
                "id": "init"
            }

            response = await self.client.post(
                f"{self.mcp_url}/mcp",
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )

            response.raise_for_status()

            # Extract session ID from response headers
            if "mcp-session-id" in response.headers:
                self.session_id = response.headers["mcp-session-id"]
                logger.info(f"MCP session initialized: {self.session_id}")
            else:
                logger.warning("No session ID received from MCP server")

        except Exception as e:
            logger.error(f"Failed to initialize MCP session: {e}")
            raise

    async def call_tool(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """
        Call an MCP tool via HTTP with retry logic.

        Args:
            tool_name: Name of the MCP tool to call
            **kwargs: Tool arguments

        Returns:
            Dict with the tool response
        """
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # Ensure session is initialized (or re-initialized on retry)
                if attempt > 0:
                    # Reset session on retry
                    self.session_id = None
                await self._ensure_session()

                # MCP tools are called via tools/call method
                request_data = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": f"mcp__archon__{tool_name}",
                        "arguments": kwargs
                    },
                    "id": 1
                }

                # Prepare headers with session ID
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }

                if self.session_id:
                    headers["mcp-session-id"] = self.session_id

                # Make HTTP request to MCP server
                response = await self.client.post(
                    f"{self.mcp_url}/mcp",
                    json=request_data,
                    headers=headers,
                )

                response.raise_for_status()

                # Handle SSE format response
                response_text = response.text.strip()
                if not response_text:
                    if attempt < max_retries:
                        logger.warning(f"Empty response from MCP server, retrying... (attempt {attempt + 1})")
                        continue
                    raise Exception("Empty response from MCP server")

                if response_text.startswith("event: message\ndata: "):
                    # Extract JSON from SSE format
                    json_part = response_text.split("data: ", 1)[1]
                    if not json_part.strip():
                        if attempt < max_retries:
                            logger.warning(f"Empty JSON data in SSE response, retrying... (attempt {attempt + 1})")
                            continue
                        raise Exception("Empty JSON data in SSE response")
                    result = json.loads(json_part)
                else:
                    if not response_text:
                        if attempt < max_retries:
                            logger.warning(f"Empty response text, retrying... (attempt {attempt + 1})")
                            continue
                        raise Exception("Empty response text")
                    result = response.json()

                if "error" in result:
                    error = result["error"]
                    raise Exception(f"MCP tool error: {error.get('message', 'Unknown error')} - {error.get('data', '')}")

                return result.get("result", {})

            except json.JSONDecodeError as e:
                if attempt < max_retries:
                    logger.warning(f"JSON decode error, retrying... (attempt {attempt + 1}): {e}")
                    continue
                logger.error(f"JSON decode error calling MCP tool {tool_name}: {e}")
                raise Exception(f"Failed to parse MCP response: {str(e)}")
            except httpx.HTTPError as e:
                if attempt < max_retries:
                    logger.warning(f"HTTP error, retrying... (attempt {attempt + 1}): {e}")
                    continue
                logger.error(f"HTTP error calling MCP tool {tool_name}: {e}")
                raise Exception(f"Failed to call MCP tool: {str(e)}")
            except Exception as e:
                if attempt < max_retries and ("Empty response" in str(e) or "Expecting value" in str(e)):
                    logger.warning(f"Connection error, retrying... (attempt {attempt + 1}): {e}")
                    continue
                logger.error(f"Error calling MCP tool {tool_name}: {e}")
                raise

    # Convenience methods for common MCP tools

    async def perform_rag_query(self, query: str, source: str = None, match_count: int = 5) -> str:
        """Perform a RAG query through MCP."""
        result = await self.call_tool(
            "perform_rag_query", query=query, source=source, match_count=match_count
        )
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def get_available_sources(self) -> str:
        """Get available sources through MCP."""
        result = await self.call_tool("get_available_sources")
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def search_code_examples(
        self, query: str, source_id: str = None, match_count: int = 5
    ) -> str:
        """Search code examples through MCP."""
        result = await self.call_tool(
            "search_code_examples", query=query, source_id=source_id, match_count=match_count
        )
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def manage_project(self, action: str, **kwargs) -> str:
        """Manage projects through MCP."""
        result = await self.call_tool("manage_project", action=action, **kwargs)
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def manage_document(self, action: str, project_id: str, **kwargs) -> str:
        """Manage documents through MCP."""
        result = await self.call_tool(
            "manage_document", action=action, project_id=project_id, **kwargs
        )
        return json.dumps(result) if isinstance(result, dict) else str(result)

    async def manage_task(self, action: str, project_id: str, **kwargs) -> str:
        """Manage tasks through MCP."""
        result = await self.call_tool("manage_task", action=action, project_id=project_id, **kwargs)
        return json.dumps(result) if isinstance(result, dict) else str(result)


# Global MCP client instance (created on first use)
_mcp_client: MCPClient | None = None


async def get_mcp_client() -> MCPClient:
    """
    Get or create the global MCP client instance.

    Returns:
        MCPClient instance
    """
    global _mcp_client

    # Always create a fresh client to avoid session issues
    if _mcp_client is not None:
        try:
            await _mcp_client.close()
        except:
            pass

    _mcp_client = MCPClient()
    return _mcp_client
