"""
Obsidian Vault Sync API

API endpoints for managing Obsidian vault synchronization with Archon's knowledge base.
"""

import os
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from ..services.obsidian_sync_service import ObsidianVaultSyncService
from ...agents.obsidian_tools import ObsidianTools
from ...agents.obsidian_tools_production import ObsidianToolsProduction
from pathlib import Path

logger = get_logger(__name__)

router = APIRouter(prefix="/api/obsidian", tags=["obsidian"])

# Global sync service instance
_sync_service: ObsidianVaultSyncService | None = None


def get_sync_service() -> ObsidianVaultSyncService:
    """Get or create the Obsidian sync service instance."""
    global _sync_service

    vault_path = os.getenv("OBSIDIAN_VAULT")
    if not vault_path:
        raise HTTPException(
            status_code=500,
            detail={"error": "OBSIDIAN_VAULT environment variable not set"},
        )

    if not os.path.isdir(vault_path):
        raise HTTPException(
            status_code=500, detail={"error": f"Vault path does not exist: {vault_path}"}
        )

    if _sync_service is None:
        _sync_service = ObsidianVaultSyncService(vault_path)

    return _sync_service


class IndexVaultRequest(BaseModel):
    knowledge_type: str = "technical"
    exclude_patterns: list[str] | None = None
    max_files: int | None = None  # For testing: limit number of files to index


class WatchVaultRequest(BaseModel):
    knowledge_type: str = "technical"


class FrontmatterUpdateRequest(BaseModel):
    path: str = Field(..., description="Vault-relative path to markdown file")
    updates: dict[str, Any] = Field(default_factory=dict, description="Frontmatter fields to set")
    merge: bool = True
    preserve_existing: bool = True


@router.get("/status")
async def get_vault_status():
    """Get current Obsidian vault sync status."""
    try:
        vault_path = os.getenv("OBSIDIAN_VAULT")
        if not vault_path:
            return {
                "configured": False,
                "vault_path": None,
                "watching": False,
                "synced_files": 0,
            }

        if not os.path.isdir(vault_path):
            return {
                "configured": True,
                "vault_path": vault_path,
                "exists": False,
                "watching": False,
                "synced_files": 0,
            }

        try:
            service = get_sync_service()
            return {
                "configured": True,
                "vault_path": vault_path,
                "exists": True,
                "watching": service.is_watching,
                "synced_files": len(service.synced_files),
            }
        except Exception:
            return {
                "configured": True,
                "vault_path": vault_path,
                "exists": True,
                "watching": False,
                "synced_files": 0,
            }

    except Exception as e:
        safe_logfire_error(f"Failed to get vault status | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/index")
async def index_vault(request: IndexVaultRequest):
    """
    Index entire Obsidian vault into knowledge base.

    This will process all markdown files in the vault and create
    knowledge base entries with embeddings for RAG search.
    """
    try:
        safe_logfire_info(
            f"Starting Obsidian vault indexing | knowledge_type={request.knowledge_type}"
        )

        service = get_sync_service()
        stats = await service.index_vault(
            knowledge_type=request.knowledge_type,
            exclude_patterns=request.exclude_patterns,
            max_files=request.max_files,
        )

        safe_logfire_info(
            f"Vault indexing complete | success={stats['success']} | failed={stats['failed']}"
        )

        return {
            "success": True,
            "message": f"Indexed {stats['success']} files, {stats['failed']} failed",
            "stats": stats,
        }

    except Exception as e:
        safe_logfire_error(f"Failed to index vault | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/watch/start")
async def start_watching(request: WatchVaultRequest):
    """Start watching Obsidian vault for file changes and auto-sync."""
    try:
        safe_logfire_info("Starting Obsidian vault file watcher")

        service = get_sync_service()

        if service.is_watching:
            return {
                "success": True,
                "message": "Vault watching already active",
                "watching": True,
            }

        service.start_watching(knowledge_type=request.knowledge_type)

        return {
            "success": True,
            "message": "Started watching Obsidian vault for changes",
            "watching": True,
        }

    except Exception as e:
        safe_logfire_error(f"Failed to start vault watching | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/watch/stop")
async def stop_watching():
    """Stop watching Obsidian vault for changes."""
    try:
        safe_logfire_info("Stopping Obsidian vault file watcher")

        service = get_sync_service()

        if not service.is_watching:
            return {
                "success": True,
                "message": "Vault watching was not active",
                "watching": False,
            }

        service.stop_watching()

        return {
            "success": True,
            "message": "Stopped watching Obsidian vault",
            "watching": False,
        }

    except Exception as e:
        safe_logfire_error(f"Failed to stop vault watching | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/vault/info")
async def get_vault_info():
    """Get information about the configured Obsidian vault."""
    try:
        vault_path = os.getenv("OBSIDIAN_VAULT")
        if not vault_path:
            raise HTTPException(
                status_code=404, detail={"error": "Obsidian vault not configured"}
            )

        if not os.path.isdir(vault_path):
            raise HTTPException(
                status_code=404, detail={"error": f"Vault not found: {vault_path}"}
            )

        # Count markdown files
        from pathlib import Path

        vault = Path(vault_path)
        total_files = len(list(vault.rglob("*.md")))

        # Get vault size
        total_size = sum(f.stat().st_size for f in vault.rglob("*") if f.is_file())
        size_mb = round(total_size / (1024 * 1024), 2)

        return {
            "vault_path": vault_path,
            "total_markdown_files": total_files,
            "total_size_mb": size_mb,
            "exists": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to get vault info | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/review/missing-tags")
async def get_missing_tag_notes():
    """Return notes missing required frontmatter classifications."""
    try:
        vault_path = os.getenv("OBSIDIAN_VAULT")
        if not vault_path:
            raise HTTPException(status_code=404, detail={"error": "Obsidian vault not configured"})

        if not os.path.isdir(vault_path):
            raise HTTPException(status_code=404, detail={"error": f"Vault not found: {vault_path}"})

        tools = ObsidianTools(vault_path)
        index = tools.scan_vault()

        notes_missing = []
        for note in index.notes:
            missing_fields: list[str] = []
            frontmatter = note.frontmatter or {}
            for field in ("area", "service", "status"):
                value = frontmatter.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    missing_fields.append(field)
            if missing_fields:
                notes_missing.append(
                    {
                        "path": note.path,
                        "title": note.title,
                        "missing": missing_fields,
                        "tags": note.tags,
                    }
                )

        return {
            "success": True,
            "total": len(notes_missing),
            "notes": notes_missing,
        }

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to gather missing tag notes | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/frontmatter/update")
async def update_frontmatter(request: FrontmatterUpdateRequest):
    """Apply frontmatter updates to an Obsidian note."""
    try:
        vault_path = os.getenv("OBSIDIAN_VAULT")
        if not vault_path:
            raise HTTPException(status_code=404, detail={"error": "Obsidian vault not configured"})

        vault_root = Path(vault_path).resolve()
        target_path = (vault_root / request.path).resolve()

        if not str(target_path).startswith(str(vault_root)):
            raise HTTPException(status_code=400, detail={"error": "Invalid note path"})

        if not target_path.exists() or not target_path.is_file():
            raise HTTPException(status_code=404, detail={"error": f"Note not found: {request.path}"})

        tools = ObsidianToolsProduction(vault_path)
        changes = tools.update_frontmatter_hygiene(
            target_path,
            request.updates,
            merge=request.merge,
            preserve_existing=request.preserve_existing,
        )

        # Return updated frontmatter snapshot for context
        updated_frontmatter, _ = tools.parse_frontmatter(target_path.read_text(encoding="utf-8"))

        return {
            "success": True,
            "changes": changes,
            "frontmatter": updated_frontmatter,
        }

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to update note frontmatter | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})
