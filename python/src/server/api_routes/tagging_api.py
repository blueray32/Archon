"""
Auto-Tagging API Routes

API endpoints for automatic tag generation and management.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config.logfire_config import get_logger
from ..services.auto_tagging_service import AutoTaggingService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagItemRequest(BaseModel):
    """Request to tag a single item."""

    source_id: str
    force: bool = False
    max_tags: int = 5


class BatchTagRequest(BaseModel):
    """Request to tag multiple items."""

    source_ids: list[str] | None = None
    knowledge_type: str | None = None
    force: bool = False
    max_items: int | None = None


@router.post("/generate")
async def tag_knowledge_item(request: TagItemRequest):
    """
    Generate and apply tags to a knowledge item.

    This analyzes the content and automatically generates relevant tags.
    """
    try:
        service = AutoTaggingService()
        success, tags = await service.tag_knowledge_item(
            source_id=request.source_id,
            force=request.force,
            max_tags=request.max_tags,
        )

        if success:
            return {
                "success": True,
                "source_id": request.source_id,
                "tags": tags,
                "message": f"Generated {len(tags)} tags",
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate tags")

    except Exception as e:
        logger.error(f"Tag generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def batch_tag_items(request: BatchTagRequest):
    """
    Tag multiple knowledge items in batch.

    This can tag all items, items of a specific type, or a specific list of items.
    """
    try:
        service = AutoTaggingService()
        stats = await service.batch_tag_items(
            source_ids=request.source_ids,
            knowledge_type=request.knowledge_type,
            force=request.force,
            max_items=request.max_items,
        )

        return {
            "success": True,
            "stats": stats,
            "message": f"Tagged {stats['success']} items with {stats['tags_generated']} total tags",
        }

    except Exception as e:
        logger.error(f"Batch tagging failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_tags():
    """
    Get all tags and their usage counts.

    Returns a dictionary mapping tag names to the number of items using each tag.
    """
    try:
        service = AutoTaggingService()
        tag_counts = await service.get_all_tags()

        # Sort by usage count
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "success": True,
            "total_unique_tags": len(sorted_tags),
            "tags": dict(sorted_tags),
            "top_tags": dict(sorted_tags[:20]),  # Top 20 most used tags
        }

    except Exception as e:
        logger.error(f"Failed to get tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_tagging_stats():
    """
    Get statistics about tags in the knowledge base.

    Returns information about tagged vs untagged items, tag distribution, etc.
    """
    try:
        from ..utils import get_supabase_client

        supabase = get_supabase_client()

        # Count total sources
        total_response = supabase.table("archon_sources").select("source_id", count="exact").execute()
        total_items = total_response.count

        # Count tagged sources
        tagged_response = (
            supabase.table("archon_sources")
            .select("source_id", count="exact")
            .not_.is_("metadata->>tags", "null")
            .execute()
        )
        tagged_items = tagged_response.count

        # Count auto-tagged sources
        auto_tagged_response = (
            supabase.table("archon_sources")
            .select("source_id", count="exact")
            .eq("metadata->>auto_tagged", "true")
            .execute()
        )
        auto_tagged_items = auto_tagged_response.count

        service = AutoTaggingService()
        tag_counts = await service.get_all_tags()

        return {
            "success": True,
            "total_items": total_items,
            "tagged_items": tagged_items,
            "untagged_items": total_items - tagged_items,
            "auto_tagged_items": auto_tagged_items,
            "manually_tagged_items": tagged_items - auto_tagged_items,
            "tagging_percentage": round((tagged_items / total_items * 100) if total_items > 0 else 0, 1),
            "unique_tags": len(tag_counts),
            "average_tags_per_item": round(sum(tag_counts.values()) / tagged_items if tagged_items > 0 else 0, 1),
        }

    except Exception as e:
        logger.error(f"Failed to get tagging stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
