"""
Obsidian Vault Management Tools for MCP Server

Provides tools for AI agents to interact with Obsidian vault sync,
including indexing operations, status checks, and file watching.
"""

import json
import logging

from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


def register_obsidian_tools(mcp):
    """Register Obsidian vault management tools with the MCP server."""

    @mcp.tool()
    async def get_obsidian_status(ctx: Context) -> str:
        """
        Get current Obsidian vault sync status.

        Returns:
            JSON with vault configuration, path, watching status, and synced files count
        """
        try:
            context = ctx.request_context.lifespan_context
            service_client = context.service_client

            result = await service_client.call_api(
                method="GET",
                endpoint="/api/obsidian/status"
            )

            return json.dumps({
                "success": True,
                "status": result,
                "message": "Vault status retrieved successfully"
            })

        except Exception as e:
            logger.error(f"Failed to get Obsidian vault status: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to get vault status: {str(e)}"
            })

    @mcp.tool()
    async def get_obsidian_vault_info(ctx: Context) -> str:
        """
        Get information about the configured Obsidian vault.

        Returns:
            JSON with vault path, total markdown files, and total size
        """
        try:
            context = ctx.request_context.lifespan_context
            service_client = context.service_client

            result = await service_client.call_api(
                method="GET",
                endpoint="/api/obsidian/vault/info"
            )

            return json.dumps({
                "success": True,
                "vault_info": result,
                "message": "Vault information retrieved successfully"
            })

        except Exception as e:
            logger.error(f"Failed to get Obsidian vault info: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to get vault info: {str(e)}"
            })

    @mcp.tool()
    async def index_obsidian_vault(
        ctx: Context,
        knowledge_type: str = "technical",
        max_files: int | None = None
    ) -> str:
        """
        Index Obsidian vault into knowledge base.

        This processes markdown files from your Obsidian vault and creates
        knowledge base entries with embeddings for RAG search.

        Args:
            knowledge_type: Knowledge type classification (default: "technical")
            max_files: Maximum number of files to index (optional, for testing)

        Returns:
            JSON with indexing results including total, success, and failed counts

        Examples:
            # Test with 10 files
            index_obsidian_vault(max_files=10)

            # Index all files
            index_obsidian_vault()

            # Index with specific knowledge type
            index_obsidian_vault(knowledge_type="project_docs")
        """
        try:
            context = ctx.request_context.lifespan_context
            service_client = context.service_client

            payload = {
                "knowledge_type": knowledge_type,
                "max_files": max_files
            }

            result = await service_client.call_api(
                method="POST",
                endpoint="/api/obsidian/index",
                data=payload
            )

            return json.dumps({
                "success": True,
                "indexing_results": result,
                "message": f"Indexed {result.get('stats', {}).get('success', 0)} files successfully"
            })

        except Exception as e:
            logger.error(f"Failed to index Obsidian vault: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to index vault: {str(e)}"
            })

    @mcp.tool()
    async def start_obsidian_watching(
        ctx: Context,
        knowledge_type: str = "technical"
    ) -> str:
        """
        Start watching Obsidian vault for file changes and auto-sync.

        When enabled, any changes you make to markdown files in Obsidian will
        automatically be synced to Archon's knowledge base.

        Args:
            knowledge_type: Default knowledge type for new/modified files

        Returns:
            JSON with success status and watching state

        Note:
            Requires watchdog library to be installed in the backend container.
        """
        try:
            context = ctx.request_context.lifespan_context
            service_client = context.service_client

            payload = {
                "knowledge_type": knowledge_type
            }

            result = await service_client.call_api(
                method="POST",
                endpoint="/api/obsidian/watch/start",
                data=payload
            )

            return json.dumps({
                "success": True,
                "watching": result.get("watching", False),
                "message": result.get("message", "Started watching vault")
            })

        except Exception as e:
            logger.error(f"Failed to start Obsidian watching: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to start watching: {str(e)}"
            })

    @mcp.tool()
    async def stop_obsidian_watching(ctx: Context) -> str:
        """
        Stop watching Obsidian vault for changes.

        Disables automatic syncing of file changes from Obsidian to Archon.

        Returns:
            JSON with success status and watching state
        """
        try:
            context = ctx.request_context.lifespan_context
            service_client = context.service_client

            result = await service_client.call_api(
                method="POST",
                endpoint="/api/obsidian/watch/stop"
            )

            return json.dumps({
                "success": True,
                "watching": result.get("watching", False),
                "message": result.get("message", "Stopped watching vault")
            })

        except Exception as e:
            logger.error(f"Failed to stop Obsidian watching: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to stop watching: {str(e)}"
            })

    @mcp.tool()
    async def list_obsidian_metadata_gaps(ctx: Context) -> str:
        """List notes missing required area/service/status frontmatter."""
        try:
            context = ctx.request_context.lifespan_context
            service_client = context.service_client

            result = await service_client.call_api(
                method="GET",
                endpoint="/api/obsidian/review/missing-tags"
            )

            return json.dumps({
                "success": True,
                "total": result.get("total", 0),
                "notes": result.get("notes", []),
                "message": "Retrieved Obsidian frontmatter gaps"
            })

        except Exception as e:
            logger.error(f"Failed to list Obsidian metadata gaps: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to retrieve metadata gaps: {str(e)}"
            })

    @mcp.tool()
    async def update_obsidian_frontmatter(
        ctx: Context,
        path: str,
        updates_json: str,
        merge: bool = True,
        preserve_existing: bool = True,
    ) -> str:
        """Update frontmatter for a vault note via backend API."""
        try:
            try:
                updates = json.loads(updates_json) if updates_json else {}
            except json.JSONDecodeError as parse_error:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid updates JSON: {parse_error}"
                })

            context = ctx.request_context.lifespan_context
            service_client = context.service_client

            payload = {
                "path": path,
                "updates": updates,
                "merge": merge,
                "preserve_existing": preserve_existing,
            }

            result = await service_client.call_api(
                method="POST",
                endpoint="/api/obsidian/frontmatter/update",
                data=payload,
            )

            return json.dumps({
                "success": True,
                "changes": result.get("changes", {}),
                "frontmatter": result.get("frontmatter", {}),
                "message": "Frontmatter updated successfully"
            })

        except Exception as e:
            logger.error(f"Failed to update Obsidian frontmatter: {e}")
            return json.dumps({
                "success": False,
                "error": f"Failed to update frontmatter: {str(e)}"
            })

    logger.info("✓ Obsidian vault tools registered")
