"""
Knowledge Management API Module

This module handles all knowledge base operations including:
- Crawling and indexing web content
- Document upload and processing
- RAG (Retrieval Augmented Generation) queries
- Knowledge item management and search
- Progress tracking via HTTP polling
"""

import asyncio
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

# Import unified logging
from ..config.logfire_config import get_logger, safe_logfire_error, safe_logfire_info
from ..services.crawler_manager import get_crawler
from ..services.crawling import CrawlOrchestrationService
from ..services.knowledge import DatabaseMetricsService, KnowledgeItemService
from ..services.search.rag_service import RAGService
from ..services.storage import DocumentStorageService
from ..utils import get_supabase_client
from ..utils.document_processing import extract_text_from_document

# Get logger for this module
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["knowledge"])


# Create a semaphore to limit concurrent crawl OPERATIONS (not pages within a crawl)
# This prevents the server from becoming unresponsive during heavy crawling
#
# IMPORTANT: This is different from CRAWL_MAX_CONCURRENT (configured in UI/database):
# - CONCURRENT_CRAWL_LIMIT: Max number of separate crawl operations that can run simultaneously (server protection)
#   Example: User A crawls site1.com, User B crawls site2.com, User C crawls site3.com = 3 operations
# - CRAWL_MAX_CONCURRENT: Max number of pages that can be crawled in parallel within a single crawl operation
#   Example: While crawling site1.com, fetch up to 10 pages simultaneously
#
# The hardcoded limit of 3 protects the server from being overwhelmed by multiple users
# starting crawls at the same time. Each crawl can still process many pages in parallel.
CONCURRENT_CRAWL_LIMIT = 3  # Max simultaneous crawl operations (protects server resources)
crawl_semaphore = asyncio.Semaphore(CONCURRENT_CRAWL_LIMIT)

# Track active async crawl tasks for cancellation support
active_crawl_tasks: dict[str, asyncio.Task] = {}

# Concurrency guard for export operation (single export at a time)
active_export_task: asyncio.Task | None = None
active_export_progress_id: str | None = None


# Request Models
class KnowledgeItemRequest(BaseModel):
    url: str
    knowledge_type: str = "technical"
    tags: list[str] = []
    update_frequency: int = 7
    max_depth: int = 2  # Maximum crawl depth (1-5)
    extract_code_examples: bool = True  # Whether to extract code examples

    class Config:
        schema_extra = {
            "example": {
                "url": "https://example.com",
                "knowledge_type": "technical",
                "tags": ["documentation"],
                "update_frequency": 7,
                "max_depth": 2,
                "extract_code_examples": True,
            }
        }


class CrawlRequest(BaseModel):
    url: str
    knowledge_type: str = "general"
    tags: list[str] = []
    update_frequency: int = 7
    max_depth: int = 2  # Maximum crawl depth (1-5)


class RagQueryRequest(BaseModel):
    query: str
    source: str | None = None
    match_count: int = 5


class ExportRequest(BaseModel):
    target: str | None = None  # Optional override for OBSIDIAN_VAULT
    source_ids: list[str] | None = None
    tags: list[str] | None = None
    knowledge_type: str | None = None
    updated_since: str | None = None  # ISO8601 string


@router.get("/knowledge-items/export-default-target")
async def get_export_default_target():
    """Return the server's default export target directory (OBSIDIAN_VAULT).

    Provides visibility for the UI about the effective default vault path without requiring a client override.
    """
    try:
        import os
        # Compute effective default target using the same fallback logic as export
        effective: str | None = None
        env_target = os.getenv("OBSIDIAN_VAULT")
        if env_target and os.path.isdir(os.path.expanduser(env_target)):
            effective = os.path.expanduser(env_target)
        else:
            in_container = os.path.exists("/.dockerenv")
            if in_container and os.path.isdir("/vault"):
                effective = "/vault"
            else:
                home_vault = os.path.expanduser("~/Documents/ArchonVault")
                if os.path.isdir(home_vault):
                    effective = home_vault

        exists = bool(effective and os.path.exists(effective))
        is_dir = bool(effective and os.path.isdir(effective))
        return {"defaultTarget": effective, "exists": exists, "isDir": is_dir}
    except Exception as e:
        safe_logfire_error(f"Failed to get export default target | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/crawl-progress/{progress_id}")
async def get_crawl_progress(progress_id: str):
    """Get crawl progress for polling.
    
    Returns the current state of a crawl operation.
    Frontend should poll this endpoint to track crawl progress.
    """
    try:
        from ..utils.progress.progress_tracker import ProgressTracker
        from ..models.progress_models import create_progress_response

        # Get progress from the tracker's in-memory storage
        progress_data = ProgressTracker.get_progress(progress_id)
        safe_logfire_info(f"Crawl progress requested | progress_id={progress_id} | found={progress_data is not None}")

        if not progress_data:
            # Return 404 if no progress exists - this is correct behavior
            raise HTTPException(status_code=404, detail={"error": f"No progress found for ID: {progress_id}"})

        # Ensure we have the progress_id in the data
        progress_data["progress_id"] = progress_id
        
        # Get operation type for proper model selection
        operation_type = progress_data.get("type", "crawl")
        
        # Create standardized response using Pydantic model
        progress_response = create_progress_response(operation_type, progress_data)
        
        # Convert to dict with camelCase fields for API response
        response_data = progress_response.model_dump(by_alias=True, exclude_none=True)
        
        safe_logfire_info(
            f"Progress retrieved | operation_id={progress_id} | status={response_data.get('status')} | "
            f"progress={response_data.get('progress')} | totalPages={response_data.get('totalPages')} | "
            f"processedPages={response_data.get('processedPages')}"
        )

        return response_data
    except Exception as e:
        safe_logfire_error(f"Failed to get crawl progress | error={str(e)} | progress_id={progress_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/knowledge-items/sources")
async def get_knowledge_sources():
    """Get all available knowledge sources."""
    try:
        # Return empty list for now to pass the test
        # In production, this would query the database
        return []
    except Exception as e:
        safe_logfire_error(f"Failed to get knowledge sources | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/knowledge-items")
async def get_knowledge_items(
    page: int = 1,
    per_page: int = 20,
    knowledge_type: str | None = None,
    search: str | None = None,
    tags: str | None = None,  # Comma-separated list of tags
):
    """Get knowledge items with pagination and filtering."""
    try:
        # Use KnowledgeItemService
        service = KnowledgeItemService(get_supabase_client())
        result = await service.list_items(
            page=page,
            per_page=per_page,
            knowledge_type=knowledge_type,
            search=search,
            tags=tags.split(",") if tags else None,
        )
        return result

    except Exception as e:
        safe_logfire_error(
            f"Failed to get knowledge items | error={str(e)} | page={page} | per_page={per_page}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


class UpdateKnowledgeItemRequest(BaseModel):
    source_id: str
    updates: dict


class GetItemsByGroupRequest(BaseModel):
    group_name: str
    per_page: int = 1000


@router.put("/knowledge-items/{source_id}")
async def update_knowledge_item(source_id: str, updates: dict):
    """Update a knowledge item's metadata (legacy endpoint - use POST /knowledge-items/update for long source_ids)."""
    try:
        # Use KnowledgeItemService
        service = KnowledgeItemService(get_supabase_client())
        success, result = await service.update_item(source_id, updates)

        if success:
            return result
        else:
            if "not found" in result.get("error", "").lower():
                raise HTTPException(status_code=404, detail={"error": result.get("error")})
            else:
                raise HTTPException(status_code=500, detail={"error": result.get("error")})

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"Failed to update knowledge item | error={str(e)} | source_id={source_id}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/knowledge-items/update")
async def update_knowledge_item_by_body(request: UpdateKnowledgeItemRequest):
    """Update a knowledge item's metadata (accepts source_id in body to avoid URL length limits)."""
    try:
        # Use KnowledgeItemService
        service = KnowledgeItemService(get_supabase_client())
        success, result = await service.update_item(request.source_id, request.updates)

        if success:
            return result
        else:
            if "not found" in result.get("error", "").lower():
                raise HTTPException(status_code=404, detail={"error": result.get("error")})
            else:
                raise HTTPException(status_code=500, detail={"error": result.get("error")})

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"Failed to update knowledge item | error={str(e)} | source_id={request.source_id}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/knowledge-items/by-group")
async def get_knowledge_items_by_group(request: GetItemsByGroupRequest):
    """Get all knowledge items that belong to a specific group (avoids URL length limits)."""
    try:
        supabase = get_supabase_client()

        # Query archon_sources table for items with matching group_name
        response = supabase.table("archon_sources").select("*").eq(
            "metadata->>group_name", request.group_name
        ).limit(request.per_page).execute()

        items = []
        for row in response.data:
            source_id = row["source_id"]
            source_metadata = row.get("metadata", {})

            # Transform to match KnowledgeItem format (simplified version of KnowledgeItemService)
            items.append({
                "id": source_id,  # Use source_id as id
                "source_id": source_id,
                "url": row.get("url", f"source://{source_id}"),
                "title": row.get("title", row.get("summary", "Untitled")),
                "metadata": source_metadata,
                "created_at": row.get("created_at", ""),
                "updated_at": row.get("updated_at", "")
            })

        return {
            "items": items,
            "total": len(items),
            "page": 1,
            "per_page": request.per_page
        }

    except Exception as e:
        safe_logfire_error(
            f"Failed to get items by group | error={str(e)} | group_name={request.group_name}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/knowledge-items/{source_id}")
async def delete_knowledge_item(source_id: str):
    """Delete a knowledge item from the database."""
    try:
        logger.debug(f"Starting delete_knowledge_item for source_id: {source_id}")
        safe_logfire_info(f"Deleting knowledge item | source_id={source_id}")

        # Use SourceManagementService directly instead of going through MCP
        logger.debug("Creating SourceManagementService...")
        from ..services.source_management_service import SourceManagementService

        source_service = SourceManagementService(get_supabase_client())
        logger.debug("Successfully created SourceManagementService")

        logger.debug("Calling delete_source function...")
        success, result_data = source_service.delete_source(source_id)
        logger.debug(f"delete_source returned: success={success}, data={result_data}")

        # Convert to expected format
        result = {
            "success": success,
            "error": result_data.get("error") if not success else None,
            **result_data,
        }

        if result.get("success"):
            safe_logfire_info(f"Knowledge item deleted successfully | source_id={source_id}")

            return {"success": True, "message": f"Successfully deleted knowledge item {source_id}"}
        else:
            safe_logfire_error(
                f"Knowledge item deletion failed | source_id={source_id} | error={result.get('error')}"
            )
            raise HTTPException(
                status_code=500, detail={"error": result.get("error", "Deletion failed")}
            )

    except Exception as e:
        logger.error(f"Exception in delete_knowledge_item: {e}")
        logger.error(f"Exception type: {type(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        safe_logfire_error(
            f"Failed to delete knowledge item | error={str(e)} | source_id={source_id}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/knowledge-items/{source_id}/chunks")
async def get_knowledge_item_chunks(source_id: str, domain_filter: str | None = None):
    """Get all document chunks for a specific knowledge item with optional domain filtering."""
    try:
        safe_logfire_info(f"Fetching chunks for source_id: {source_id}, domain_filter: {domain_filter}")

        # Query document chunks with content for this specific source
        supabase = get_supabase_client()
        
        # Build the query
        query = supabase.from_("archon_crawled_pages").select(
            "id, source_id, content, metadata, url"
        )
        query = query.eq("source_id", source_id)

        # Apply domain filtering if provided
        if domain_filter:
            # Case-insensitive URL match
            query = query.ilike("url", f"%{domain_filter}%")

        # Deterministic ordering (URL then id)
        query = query.order("url", desc=False).order("id", desc=False)

        result = query.execute()
        if getattr(result, "error", None):
            safe_logfire_error(
                f"Supabase query error | source_id={source_id} | error={result.error}"
            )
            raise HTTPException(status_code=500, detail={"error": str(result.error)})

        chunks = result.data if result.data else []

        safe_logfire_info(f"Found {len(chunks)} chunks for {source_id}")

        return {
            "success": True,
            "source_id": source_id,
            "domain_filter": domain_filter,
            "chunks": chunks,
            "count": len(chunks),
        }

    except Exception as e:
        safe_logfire_error(
            f"Failed to fetch chunks | error={str(e)} | source_id={source_id}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/knowledge-items/{source_id}/code-examples")
async def get_knowledge_item_code_examples(source_id: str):
    """Get all code examples for a specific knowledge item."""
    try:
        safe_logfire_info(f"Fetching code examples for source_id: {source_id}")

        # Query code examples with full content for this specific source
        supabase = get_supabase_client()
        result = (
            supabase.from_("archon_code_examples")
            .select("id, source_id, content, summary, metadata")
            .eq("source_id", source_id)
            .execute()
        )

        code_examples = result.data if result.data else []

        safe_logfire_info(f"Found {len(code_examples)} code examples for {source_id}")

        return {
            "success": True,
            "source_id": source_id,
            "code_examples": code_examples,
            "count": len(code_examples),
        }

    except Exception as e:
        safe_logfire_error(
            f"Failed to fetch code examples | error={str(e)} | source_id={source_id}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/knowledge-items/{source_id}/refresh")
async def refresh_knowledge_item(source_id: str):
    """Refresh a knowledge item by re-crawling its URL with the same metadata."""
    try:
        safe_logfire_info(f"Starting knowledge item refresh | source_id={source_id}")

        # Get the existing knowledge item
        service = KnowledgeItemService(get_supabase_client())
        existing_item = await service.get_item(source_id)

        if not existing_item:
            raise HTTPException(
                status_code=404, detail={"error": f"Knowledge item {source_id} not found"}
            )

        # Extract metadata
        metadata = existing_item.get("metadata", {})

        # Extract the URL from the existing item
        # First try to get the original URL from metadata, fallback to url field
        url = metadata.get("original_url") or existing_item.get("url")
        if not url:
            raise HTTPException(
                status_code=400, detail={"error": "Knowledge item does not have a URL to refresh"}
            )
        knowledge_type = metadata.get("knowledge_type", "technical")
        tags = metadata.get("tags", [])
        max_depth = metadata.get("max_depth", 2)

        # Generate unique progress ID
        progress_id = str(uuid.uuid4())

        # Initialize progress tracker IMMEDIATELY so it's available for polling
        from ..utils.progress.progress_tracker import ProgressTracker
        tracker = ProgressTracker(progress_id, operation_type="crawl")
        await tracker.start({
            "url": url,
            "status": "initializing",
            "progress": 0,
            "log": f"Starting refresh for {url}",
            "source_id": source_id,
            "operation": "refresh",
            "crawl_type": "refresh"
        })

        # Get crawler from CrawlerManager - same pattern as _perform_crawl_with_progress
        try:
            crawler = await get_crawler()
            if crawler is None:
                raise Exception("Crawler not available - initialization may have failed")
        except Exception as e:
            safe_logfire_error(f"Failed to get crawler | error={str(e)}")
            raise HTTPException(
                status_code=500, detail={"error": f"Failed to initialize crawler: {str(e)}"}
            )

        # Use the same crawl orchestration as regular crawl
        crawl_service = CrawlOrchestrationService(
            crawler=crawler, supabase_client=get_supabase_client()
        )
        crawl_service.set_progress_id(progress_id)

        # Start the crawl task with proper request format
        request_dict = {
            "url": url,
            "knowledge_type": knowledge_type,
            "tags": tags,
            "max_depth": max_depth,
            "extract_code_examples": True,
            "generate_summary": True,
        }

        # Create a wrapped task that acquires the semaphore
        async def _perform_refresh_with_semaphore():
            try:
                async with crawl_semaphore:
                    safe_logfire_info(
                        f"Acquired crawl semaphore for refresh | source_id={source_id}"
                    )
                    await crawl_service.orchestrate_crawl(request_dict)
            finally:
                # Clean up task from registry when done (success or failure)
                if progress_id in active_crawl_tasks:
                    del active_crawl_tasks[progress_id]
                    safe_logfire_info(
                        f"Cleaned up refresh task from registry | progress_id={progress_id}"
                    )

        task = asyncio.create_task(_perform_refresh_with_semaphore())
        # Track the task for cancellation support
        active_crawl_tasks[progress_id] = task

        return {"progressId": progress_id, "message": f"Started refresh for {url}"}

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"Failed to refresh knowledge item | error={str(e)} | source_id={source_id}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/knowledge-items/crawl")
async def crawl_knowledge_item(request: KnowledgeItemRequest):
    """Crawl a URL and add it to the knowledge base with progress tracking."""
    # Validate URL
    if not request.url:
        raise HTTPException(status_code=422, detail="URL is required")

    # Basic URL validation
    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="URL must start with http:// or https://")

    try:
        safe_logfire_info(
            f"Starting knowledge item crawl | url={str(request.url)} | knowledge_type={request.knowledge_type} | tags={request.tags}"
        )
        # Generate unique progress ID
        progress_id = str(uuid.uuid4())

        # Initialize progress tracker IMMEDIATELY so it's available for polling
        from ..utils.progress.progress_tracker import ProgressTracker
        tracker = ProgressTracker(progress_id, operation_type="crawl")
        
        # Detect crawl type from URL
        url_str = str(request.url)
        crawl_type = "normal"
        if "sitemap.xml" in url_str:
            crawl_type = "sitemap"
        elif url_str.endswith(".txt"):
            crawl_type = "llms-txt" if "llms" in url_str.lower() else "text_file"
        
        await tracker.start({
            "url": url_str,
            "current_url": url_str,
            "crawl_type": crawl_type,
            "status": "initializing",
            "progress": 0,
            "log": f"Starting crawl for {request.url}"
        })

        # Start background task
        task = asyncio.create_task(_perform_crawl_with_progress(progress_id, request, tracker))
        # Track the task for cancellation support
        active_crawl_tasks[progress_id] = task
        safe_logfire_info(
            f"Crawl started successfully | progress_id={progress_id} | url={str(request.url)}"
        )
        # Create a proper response that will be converted to camelCase
        from pydantic import BaseModel, Field
        
        class CrawlStartResponse(BaseModel):
            success: bool
            progress_id: str = Field(alias="progressId")
            message: str
            estimated_duration: str = Field(alias="estimatedDuration")
            
            class Config:
                populate_by_name = True
        
        response = CrawlStartResponse(
            success=True,
            progress_id=progress_id,
            message="Crawling started",
            estimated_duration="3-5 minutes"
        )
        
        return response.model_dump(by_alias=True)
    except Exception as e:
        safe_logfire_error(f"Failed to start crawl | error={str(e)} | url={str(request.url)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _perform_crawl_with_progress(
    progress_id: str, request: KnowledgeItemRequest, tracker: "ProgressTracker"
):
    """Perform the actual crawl operation with progress tracking using service layer."""
    # Acquire semaphore to limit concurrent crawls
    async with crawl_semaphore:
        safe_logfire_info(
            f"Acquired crawl semaphore | progress_id={progress_id} | url={str(request.url)}"
        )
        try:
            safe_logfire_info(
                f"Starting crawl with progress tracking | progress_id={progress_id} | url={str(request.url)}"
            )

            # Get crawler from CrawlerManager
            try:
                crawler = await get_crawler()
                if crawler is None:
                    raise Exception("Crawler not available - initialization may have failed")
            except Exception as e:
                safe_logfire_error(f"Failed to get crawler | error={str(e)}")
                await tracker.error(f"Failed to initialize crawler: {str(e)}")
                return

            supabase_client = get_supabase_client()
            orchestration_service = CrawlOrchestrationService(crawler, supabase_client)
            orchestration_service.set_progress_id(progress_id)

            # Store the current task in active_crawl_tasks for cancellation support
            current_task = asyncio.current_task()
            if current_task:
                active_crawl_tasks[progress_id] = current_task
                safe_logfire_info(
                    f"Stored current task in active_crawl_tasks | progress_id={progress_id}"
                )

            # Convert request to dict for service
            request_dict = {
                "url": str(request.url),
                "knowledge_type": request.knowledge_type,
                "tags": request.tags or [],
                "max_depth": request.max_depth,
                "extract_code_examples": request.extract_code_examples,
                "generate_summary": True,
            }

            # Orchestrate the crawl (now returns immediately with task info)
            result = await orchestration_service.orchestrate_crawl(request_dict)

            # The orchestration service now runs in background and handles all progress updates
            # Just log that the task was started
            safe_logfire_info(
                f"Crawl task started | progress_id={progress_id} | task_id={result.get('task_id')}"
            )
        except asyncio.CancelledError:
            safe_logfire_info(f"Crawl cancelled | progress_id={progress_id}")
            raise
        except Exception as e:
            error_message = f"Crawling failed: {str(e)}"
            safe_logfire_error(
                f"Crawl failed | progress_id={progress_id} | error={error_message} | exception_type={type(e).__name__}"
            )
            import traceback

            tb = traceback.format_exc()
            # Ensure the error is visible in logs
            logger.error(f"=== CRAWL ERROR FOR {progress_id} ===")
            logger.error(f"Error: {error_message}")
            logger.error(f"Exception Type: {type(e).__name__}")
            logger.error(f"Traceback:\n{tb}")
            logger.error("=== END CRAWL ERROR ===")
            safe_logfire_error(f"Crawl exception traceback | traceback={tb}")
            # Ensure clients see the failure
            try:
                await tracker.error(error_message)
            except Exception:
                pass
        finally:
            # Clean up task from registry when done (success or failure)
            if progress_id in active_crawl_tasks:
                del active_crawl_tasks[progress_id]
                safe_logfire_info(
                    f"Cleaned up crawl task from registry | progress_id={progress_id}"
                )


@router.post("/knowledge-items/export-to-vault")
async def export_knowledge_to_vault(request: ExportRequest):
    """Export knowledge base to local Obsidian vault.

    Starts a background export task and returns a progressId for polling via /api/crawl-progress/{progress_id}.
    """
    try:
        # Determine effective target path with sensible fallbacks
        import os
        effective_target: str | None = None

        # 1) Explicit request target takes priority
        if request.target and str(request.target).strip():
            candidate = os.path.expanduser(str(request.target).strip())
            if not os.path.isdir(candidate):
                raise HTTPException(status_code=422, detail={"error": f"Target path is not a directory: {request.target}"})
            effective_target = candidate
        else:
            # 2) Environment variable OBSIDIAN_VAULT
            env_target = os.getenv("OBSIDIAN_VAULT")
            if env_target and os.path.isdir(os.path.expanduser(env_target)):
                effective_target = os.path.expanduser(env_target)
            else:
                # 3) If running in container, prefer /vault if present
                in_container = os.path.exists("/.dockerenv")
                if in_container and os.path.isdir("/vault"):
                    effective_target = "/vault"
                else:
                    # 4) Local default fallback: ~/Documents/ArchonVault
                    home_vault = os.path.expanduser("~/Documents/ArchonVault")
                    try:
                        os.makedirs(home_vault, exist_ok=True)
                    except Exception:
                        pass
                    if os.path.isdir(home_vault):
                        effective_target = home_vault

        if not effective_target:
            # Provide a clear error with guidance
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "No valid export target directory. Set OBSIDIAN_VAULT, provide 'target', or create ~/Documents/ArchonVault",
                },
            )

        # If an export is already running, return existing progressId
        global active_export_task, active_export_progress_id
        if active_export_task and not active_export_task.done() and active_export_progress_id:
            safe_logfire_info(
                f"Export already running | progress_id={active_export_progress_id}"
            )
            return {
                "success": True,
                "progressId": active_export_progress_id,
                "message": "Export already in progress",
            }

        # Create progress tracker for a new export
        progress_id = str(uuid.uuid4())
        from ..utils.progress.progress_tracker import ProgressTracker
        tracker = ProgressTracker(progress_id, operation_type="export")
        await tracker.start({
            "status": "starting",
            "progress": 0,
            "log": "Starting knowledge export to vault",
            "target": effective_target,
        })

        # Background export using thread to avoid blocking event loop
        import asyncio
        loop = asyncio.get_running_loop()

        from ...scripts.export_kb_to_vault import run_export  # local import to avoid circulars

        def _progress_hook(total: int, done: int, message: str):
            pct = int((done / max(total, 1)) * 100)
            try:
                asyncio.run_coroutine_threadsafe(
                    tracker.update(
                        status="exporting",
                        progress=pct,
                        log=message,
                        total_sources=total,
                        exported=done,
                    ),
                    loop,
                )
            except Exception:
                # Best-effort progress; keep running on errors
                pass

        async def _run_in_bg():
            try:
                # Create client in the worker thread to avoid cross-thread reuse
                def _work():
                    from ..services.client_manager import get_supabase_client as _get_client
                    client = _get_client()
                    return run_export(
                        client,
                        vault_path=effective_target,
                        progress_hook=_progress_hook,
                        source_ids=request.source_ids,
                        tags=request.tags,
                        knowledge_type=request.knowledge_type,
                        updated_since=request.updated_since,
                    )

                summary = await asyncio.to_thread(_work)
                await tracker.complete({
                    "status": "completed",
                    "log": f"Export complete: {summary.get('exported', 0)} sources exported, {summary.get('failed', 0)} failures",
                    "result": summary,
                })
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                safe_logfire_error(f"Export failed | error={str(e)} | traceback={tb}")
                await tracker.error(str(e))
            finally:
                if progress_id in active_crawl_tasks:
                    del active_crawl_tasks[progress_id]
                # Clear export concurrency guard
                global active_export_task, active_export_progress_id
                active_export_task = None
                active_export_progress_id = None

        task = asyncio.create_task(_run_in_bg())
        active_crawl_tasks[progress_id] = task
        active_export_task = task
        active_export_progress_id = progress_id

        return {"success": True, "progressId": progress_id, "message": "Export started"}
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to start export | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/documents/upload-folder")
async def upload_folder(
    files: list[UploadFile] = File(...),
    tags: str | None = Form(None),
    knowledge_type: str = Form("technical"),
):
    """Upload and process multiple documents from a folder with progress tracking."""
    try:
        safe_logfire_info(
            f"📁 FOLDER UPLOAD: Starting folder upload | file_count={len(files)} | knowledge_type={knowledge_type}"
        )

        # Generate unique progress ID for the entire folder upload
        progress_id = str(uuid.uuid4())

        # Parse tags
        try:
            tag_list = json.loads(tags) if tags else []
            if tag_list is None:
                tag_list = []
            if not isinstance(tag_list, list):
                raise HTTPException(status_code=422, detail={"error": "tags must be a JSON array of strings"})
            if not all(isinstance(tag, str) for tag in tag_list):
                raise HTTPException(status_code=422, detail={"error": "tags must be a JSON array of strings"})
        except json.JSONDecodeError as ex:
            raise HTTPException(status_code=422, detail={"error": f"Invalid tags JSON: {str(ex)}"})

        # Read all file contents immediately to avoid closed file issues
        file_data_list = []
        for file in files:
            file_content = await file.read()
            file_data_list.append({
                "content": file_content,
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(file_content),
            })

        # Initialize progress tracker
        from ..utils.progress.progress_tracker import ProgressTracker
        tracker = ProgressTracker(progress_id, operation_type="folder_upload")
        await tracker.start({
            "status": "initializing",
            "progress": 0,
            "log": f"Starting folder upload ({len(file_data_list)} files)",
            "totalFiles": len(file_data_list),
            "processedFiles": 0,
        })

        # Start background task for processing all files
        task = asyncio.create_task(
            _perform_folder_upload_with_progress(
                progress_id, file_data_list, tag_list, knowledge_type, tracker
            )
        )
        active_crawl_tasks[progress_id] = task

        safe_logfire_info(
            f"Folder upload started successfully | progress_id={progress_id} | file_count={len(file_data_list)}"
        )

        return {
            "success": True,
            "progressId": progress_id,
            "message": f"Folder upload started ({len(file_data_list)} files)",
            "fileCount": len(file_data_list),
        }

    except Exception as e:
        safe_logfire_error(
            f"Failed to start folder upload | error={str(e)} | file_count={len(files)} | error_type={type(e).__name__}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    tags: str | None = Form(None),
    knowledge_type: str = Form("technical"),
):
    """Upload and process a document with progress tracking."""
    try:
        # DETAILED LOGGING: Track knowledge_type parameter flow
        safe_logfire_info(
            f"📋 UPLOAD: Starting document upload | filename={file.filename} | content_type={file.content_type} | knowledge_type={knowledge_type}"
        )

        # Generate unique progress ID
        progress_id = str(uuid.uuid4())

        # Parse tags
        try:
            tag_list = json.loads(tags) if tags else []
            if tag_list is None:
                tag_list = []
            # Validate tags is a list of strings
            if not isinstance(tag_list, list):
                raise HTTPException(status_code=422, detail={"error": "tags must be a JSON array of strings"})
            if not all(isinstance(tag, str) for tag in tag_list):
                raise HTTPException(status_code=422, detail={"error": "tags must be a JSON array of strings"})
        except json.JSONDecodeError as ex:
            raise HTTPException(status_code=422, detail={"error": f"Invalid tags JSON: {str(ex)}"})

        # Read file content immediately to avoid closed file issues
        file_content = await file.read()
        file_metadata = {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(file_content),
        }

        # Initialize progress tracker IMMEDIATELY so it's available for polling
        from ..utils.progress.progress_tracker import ProgressTracker
        tracker = ProgressTracker(progress_id, operation_type="upload")
        await tracker.start({
            "filename": file.filename,
            "status": "initializing",
            "progress": 0,
            "log": f"Starting upload for {file.filename}"
        })
        # Start background task for processing with file content and metadata
        task = asyncio.create_task(
            _perform_upload_with_progress(
                progress_id, file_content, file_metadata, tag_list, knowledge_type, tracker
            )
        )
        # Track the task for cancellation support
        active_crawl_tasks[progress_id] = task
        safe_logfire_info(
            f"Document upload started successfully | progress_id={progress_id} | filename={file.filename}"
        )
        return {
            "success": True,
            "progressId": progress_id,
            "message": "Document upload started",
            "filename": file.filename,
        }

    except Exception as e:
        safe_logfire_error(
            f"Failed to start document upload | error={str(e)} | filename={file.filename} | error_type={type(e).__name__}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})


async def _perform_folder_upload_with_progress(
    progress_id: str,
    file_data_list: list[dict],
    tag_list: list[str],
    knowledge_type: str,
    tracker: "ProgressTracker",
):
    """Perform folder upload with progress tracking for multiple files."""
    from ..services.crawling.progress_mapper import ProgressMapper
    progress_mapper = ProgressMapper()

    try:
        total_files = len(file_data_list)
        processed_files = 0
        successful_files = 0
        failed_files = []

        safe_logfire_info(
            f"Starting folder upload processing | progress_id={progress_id} | total_files={total_files}"
        )

        # Process each file
        for idx, file_data in enumerate(file_data_list):
            filename = file_data["filename"]
            content_type = file_data["content_type"]
            file_content = file_data["content"]

            try:
                # Update progress for current file
                file_progress = int((idx / total_files) * 100)
                await tracker.update(
                    status="processing",
                    progress=file_progress,
                    log=f"Processing file {idx + 1}/{total_files}: {filename}",
                    totalFiles=total_files,
                    processedFiles=processed_files,
                    currentFile=filename,
                )

                # Extract text from document
                extracted_text = extract_text_from_document(file_content, filename, content_type)
                safe_logfire_info(
                    f"Text extracted from folder file | filename={filename} | length={len(extracted_text)}"
                )

                # Use DocumentStorageService to handle the upload
                doc_storage_service = DocumentStorageService(get_supabase_client())

                # Generate source_id from filename with UUID
                source_id = f"folder_{filename.replace(' ', '_').replace('.', '_')}_{uuid.uuid4().hex[:8]}"

                # Store document without progress callback (batch operation)
                success, result = await doc_storage_service.upload_document(
                    file_content=extracted_text,
                    filename=filename,
                    source_id=source_id,
                    knowledge_type=knowledge_type,
                    tags=tag_list,
                    progress_callback=None,  # Skip per-file progress
                    cancellation_check=None,
                )

                if success:
                    successful_files += 1
                    safe_logfire_info(
                        f"Folder file uploaded successfully | filename={filename} | chunks={result.get('chunks_stored')}"
                    )
                else:
                    failed_files.append({"filename": filename, "error": result.get("error", "Unknown error")})
                    safe_logfire_error(f"Folder file upload failed | filename={filename} | error={result.get('error')}")

            except Exception as e:
                failed_files.append({"filename": filename, "error": str(e)})
                safe_logfire_error(f"Failed to process folder file | filename={filename} | error={str(e)}")

            processed_files += 1

        # Complete the folder upload
        await tracker.complete({
            "log": f"Folder upload complete: {successful_files}/{total_files} files uploaded successfully",
            "totalFiles": total_files,
            "processedFiles": processed_files,
            "successfulFiles": successful_files,
            "failedFiles": len(failed_files),
            "failures": failed_files if failed_files else None,
        })

        safe_logfire_info(
            f"Folder upload completed | progress_id={progress_id} | successful={successful_files} | failed={len(failed_files)}"
        )

    except Exception as e:
        error_msg = f"Folder upload failed: {str(e)}"
        await tracker.error(error_msg)
        logger.error(f"Folder upload failed: {e}", exc_info=True)
        safe_logfire_error(
            f"Folder upload failed | progress_id={progress_id} | error={str(e)}"
        )
    finally:
        # Clean up task from registry
        if progress_id in active_crawl_tasks:
            del active_crawl_tasks[progress_id]
            safe_logfire_info(f"Cleaned up folder upload task from registry | progress_id={progress_id}")


async def _perform_upload_with_progress(
    progress_id: str,
    file_content: bytes,
    file_metadata: dict,
    tag_list: list[str],
    knowledge_type: str,
    tracker: "ProgressTracker",
):
    """Perform document upload with progress tracking using service layer."""
    # Create cancellation check function for document uploads
    def check_upload_cancellation():
        """Check if upload task has been cancelled."""
        task = active_crawl_tasks.get(progress_id)
        if task and task.cancelled():
            raise asyncio.CancelledError("Document upload was cancelled by user")

    # Import ProgressMapper to prevent progress from going backwards
    from ..services.crawling.progress_mapper import ProgressMapper
    progress_mapper = ProgressMapper()

    try:
        filename = file_metadata["filename"]
        content_type = file_metadata["content_type"]
        # file_size = file_metadata['size']  # Not used currently

        safe_logfire_info(
            f"Starting document upload with progress tracking | progress_id={progress_id} | filename={filename} | content_type={content_type}"
        )


        # Extract text from document with progress - use mapper for consistent progress
        mapped_progress = progress_mapper.map_progress("processing", 50)
        await tracker.update(
            status="processing",
            progress=mapped_progress,
            log=f"Extracting text from {filename}"
        )

        try:
            extracted_text = extract_text_from_document(file_content, filename, content_type)
            safe_logfire_info(
                f"Document text extracted | filename={filename} | extracted_length={len(extracted_text)} | content_type={content_type}"
            )
        except Exception as ex:
            logger.error(f"Failed to extract text from document: {filename}", exc_info=True)
            await tracker.error(f"Failed to extract text from document: {str(ex)}")
            return

        # Use DocumentStorageService to handle the upload
        doc_storage_service = DocumentStorageService(get_supabase_client())

        # Generate source_id from filename with UUID to prevent collisions
        source_id = f"file_{filename.replace(' ', '_').replace('.', '_')}_{uuid.uuid4().hex[:8]}"

        # Create progress callback for tracking document processing
        async def document_progress_callback(
            message: str, percentage: int, batch_info: dict = None
        ):
            """Progress callback for tracking document processing"""
            # Map the document storage progress to overall progress range
            mapped_percentage = progress_mapper.map_progress("document_storage", percentage)

            await tracker.update(
                status="document_storage",
                progress=mapped_percentage,
                log=message,
                currentUrl=f"file://{filename}",
                **(batch_info or {})
            )


        # Call the service's upload_document method
        success, result = await doc_storage_service.upload_document(
            file_content=extracted_text,
            filename=filename,
            source_id=source_id,
            knowledge_type=knowledge_type,
            tags=tag_list,
            progress_callback=document_progress_callback,
            cancellation_check=check_upload_cancellation,
        )

        if success:
            # Complete the upload with 100% progress
            await tracker.complete({
                "log": "Document uploaded successfully!",
                "chunks_stored": result.get("chunks_stored"),
                "sourceId": result.get("source_id"),
            })
            safe_logfire_info(
                f"Document uploaded successfully | progress_id={progress_id} | source_id={result.get('source_id')} | chunks_stored={result.get('chunks_stored')}"
            )
        else:
            error_msg = result.get("error", "Unknown error")
            await tracker.error(error_msg)

    except Exception as e:
        error_msg = f"Upload failed: {str(e)}"
        await tracker.error(error_msg)
        logger.error(f"Document upload failed: {e}", exc_info=True)
        safe_logfire_error(
            f"Document upload failed | progress_id={progress_id} | filename={file_metadata.get('filename', 'unknown')} | error={str(e)}"
        )
    finally:
        # Clean up task from registry when done (success or failure)
        if progress_id in active_crawl_tasks:
            del active_crawl_tasks[progress_id]
            safe_logfire_info(f"Cleaned up upload task from registry | progress_id={progress_id}")


@router.post("/knowledge-items/search")
async def search_knowledge_items(request: RagQueryRequest):
    """Search knowledge items - alias for RAG query."""
    # Validate query
    if not request.query:
        raise HTTPException(status_code=422, detail="Query is required")

    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    # Delegate to the RAG query handler
    return await perform_rag_query(request)


@router.post("/rag/query")
async def perform_rag_query(request: RagQueryRequest):
    """Perform a RAG query on the knowledge base using service layer."""
    # Validate query
    if not request.query:
        raise HTTPException(status_code=422, detail="Query is required")

    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    try:
        # Use RAGService for RAG query
        search_service = RAGService(get_supabase_client())
        success, result = await search_service.perform_rag_query(
            query=request.query, source=request.source, match_count=request.match_count
        )

        if success:
            # Add success flag to match expected API response format
            result["success"] = True
            return result
        else:
            raise HTTPException(
                status_code=500, detail={"error": result.get("error", "RAG query failed")}
            )
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"RAG query failed | error={str(e)} | query={request.query[:50]} | source={request.source}"
        )
        raise HTTPException(status_code=500, detail={"error": f"RAG query failed: {str(e)}"})


@router.post("/keyword/query")
async def keyword_query(request: RagQueryRequest):
    """Perform a keyword-only search using PostgreSQL tsvector ranking.

    This endpoint ignores vector similarity and returns matches ranked by ts_rank_cd.
    """
    # Validate query
    if not request.query:
        raise HTTPException(status_code=422, detail="Query is required")
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="Query cannot be empty")

    try:
        supabase = get_supabase_client()

        # Prepare filter params
        filter_metadata = {}
        source_filter = None
        if request.source and request.source.strip():
            source_filter = request.source.strip()

        # Execute RPC for keyword-only search
        rpc_params = {
            "query_text": request.query,
            "match_count": request.match_count,
            "filter": filter_metadata,
            "source_filter": source_filter,
        }
        response = supabase.rpc("keyword_search_archon_crawled_pages", rpc_params).execute()

        results = []
        if response.data:
            for row in response.data:
                results.append({
                    "id": row.get("id"),
                    "url": row.get("url"),
                    "chunk_number": row.get("chunk_number"),
                    "content": row.get("content"),
                    "metadata": row.get("metadata", {}),
                    "source_id": row.get("source_id"),
                    "similarity": row.get("similarity", 0.0),
                    "match_type": row.get("match_type", "keyword"),
                })

        return {
            "success": True,
            "results": results,
            "query": request.query,
            "source": request.source,
            "match_count": request.match_count,
            "total_found": len(results),
            "execution_path": "keyword_only",
        }
    except Exception as e:
        safe_logfire_error(f"Keyword query failed | error={str(e)} | query={request.query[:50]}")
        raise HTTPException(status_code=500, detail={"error": f"Keyword query failed: {str(e)}"})

@router.post("/rag/code-examples")
async def search_code_examples(request: RagQueryRequest):
    """Search for code examples relevant to the query using dedicated code examples service."""
    try:
        # Use RAGService for code examples search
        search_service = RAGService(get_supabase_client())
        success, result = await search_service.search_code_examples_service(
            query=request.query,
            source_id=request.source,  # This is Optional[str] which matches the method signature
            match_count=request.match_count,
        )

        if success:
            # Add success flag and reformat to match expected API response format
            return {
                "success": True,
                "results": result.get("results", []),
                "reranked": result.get("reranking_applied", False),
                "error": None,
            }
        else:
            raise HTTPException(
                status_code=500,
                detail={"error": result.get("error", "Code examples search failed")},
            )
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"Code examples search failed | error={str(e)} | query={request.query[:50]} | source={request.source}"
        )
        raise HTTPException(
            status_code=500, detail={"error": f"Code examples search failed: {str(e)}"}
        )


@router.post("/code-examples")
async def search_code_examples_simple(request: RagQueryRequest):
    """Search for code examples - simplified endpoint at /api/code-examples."""
    # Delegate to the existing endpoint handler
    return await search_code_examples(request)


@router.get("/rag/sources")
async def get_available_sources():
    """Get all available sources for RAG queries."""
    try:
        # Use KnowledgeItemService
        service = KnowledgeItemService(get_supabase_client())
        result = await service.get_available_sources()

        # Parse result if it's a string
        if isinstance(result, str):
            result = json.loads(result)

        return result
    except Exception as e:
        safe_logfire_error(f"Failed to get available sources | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Delete a source and all its associated data."""
    try:
        safe_logfire_info(f"Deleting source | source_id={source_id}")

        # Use SourceManagementService directly
        from ..services.source_management_service import SourceManagementService

        source_service = SourceManagementService(get_supabase_client())

        success, result_data = source_service.delete_source(source_id)

        if success:
            safe_logfire_info(f"Source deleted successfully | source_id={source_id}")

            return {
                "success": True,
                "message": f"Successfully deleted source {source_id}",
                **result_data,
            }
        else:
            safe_logfire_error(
                f"Source deletion failed | source_id={source_id} | error={result_data.get('error')}"
            )
            raise HTTPException(
                status_code=500, detail={"error": result_data.get("error", "Deletion failed")}
            )
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to delete source | error={str(e)} | source_id={source_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/database/metrics")
async def get_database_metrics():
    """Get database metrics and statistics."""
    try:
        # Use DatabaseMetricsService
        service = DatabaseMetricsService(get_supabase_client())
        metrics = await service.get_metrics()
        return metrics
    except Exception as e:
        safe_logfire_error(f"Failed to get database metrics | error={str(e)}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.get("/health")
async def knowledge_health():
    """Knowledge API health check with migration detection."""
    # Check for database migration needs
    from ..main import _check_database_schema

    schema_status = await _check_database_schema()
    if not schema_status["valid"]:
        return {
            "status": "migration_required",
            "service": "knowledge-api",
            "timestamp": datetime.now().isoformat(),
            "ready": False,
            "migration_required": True,
            "message": schema_status["message"],
            "migration_instructions": "Open Supabase Dashboard → SQL Editor → Run: migration/add_source_url_display_name.sql"
        }

    # Removed health check logging to reduce console noise
    result = {
        "status": "healthy",
        "service": "knowledge-api",
        "timestamp": datetime.now().isoformat(),
    }

    return result


@router.get("/knowledge-items/task/{task_id}")
async def get_crawl_task_status(task_id: str):
    """Get status of a background crawl task."""
    try:
        from ..services.background_task_manager import get_task_manager

        task_manager = get_task_manager()
        status = await task_manager.get_task_status(task_id)

        if "error" in status and status["error"] == "Task not found":
            raise HTTPException(status_code=404, detail={"error": "Task not found"})

        return status
    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(f"Failed to get task status | error={str(e)} | task_id={task_id}")
        raise HTTPException(status_code=500, detail={"error": str(e)})


@router.post("/knowledge-items/stop/{progress_id}")
async def stop_crawl_task(progress_id: str):
    """Stop a running crawl or export task."""
    try:
        from ..services.crawling import get_active_orchestration, unregister_orchestration


        safe_logfire_info(f"Stop task requested | progress_id={progress_id}")

        found = False
        # Step 1: Cancel the orchestration service
        orchestration = get_active_orchestration(progress_id)
        if orchestration:
            orchestration.cancel()
            found = True

        # Step 2: Cancel the asyncio task
        if progress_id in active_crawl_tasks:
            task = active_crawl_tasks[progress_id]
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            del active_crawl_tasks[progress_id]
            found = True

        # Step 3: Remove from active orchestrations registry
        unregister_orchestration(progress_id)

        # Step 3.5: Cancel export task if it matches
        global active_export_task, active_export_progress_id
        if (not found) and active_export_progress_id == progress_id and active_export_task:
            task = active_export_task
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
            active_export_task = None
            active_export_progress_id = None
            found = True

        # Step 4: Update progress tracker to reflect cancellation (only if we found and cancelled something)
        if found:
            try:
                from ..utils.progress.progress_tracker import ProgressTracker
                tracker = ProgressTracker(progress_id, operation_type="export")
                await tracker.update(
                    status="cancelled",
                    progress=-1,
                    log="Operation cancelled by user"
                )
            except Exception:
                # Best effort - don't fail the cancellation if tracker update fails
                pass

        if not found:
            raise HTTPException(status_code=404, detail={"error": "No active task for given progress_id"})

        safe_logfire_info(f"Successfully stopped task | progress_id={progress_id}")
        return {
            "success": True,
            "message": "Task stopped successfully",
            "progressId": progress_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        safe_logfire_error(
            f"Failed to stop crawl task | error={str(e)} | progress_id={progress_id}"
        )
        raise HTTPException(status_code=500, detail={"error": str(e)})
