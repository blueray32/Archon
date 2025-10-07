"""
Auto-Tagging Service

Automatically generates relevant tags for knowledge items using AI analysis.
Analyzes content, metadata, and context to assign meaningful tags.
"""

import json
from typing import Any

from openai import OpenAI

from ..config.logfire_config import get_logger
from ..utils import get_supabase_client

logger = get_logger(__name__)


class AutoTaggingService:
    """Service for automatically generating and managing tags for knowledge items."""

    def __init__(self):
        """Initialize the auto-tagging service."""
        self.supabase = get_supabase_client()
        self.client = OpenAI()

    async def generate_tags(
        self,
        content: str,
        title: str | None = None,
        existing_metadata: dict[str, Any] | None = None,
        max_tags: int = 5,
    ) -> list[str]:
        """
        Generate relevant tags for content using AI analysis.

        Args:
            content: The text content to analyze
            title: Optional title of the content
            existing_metadata: Optional existing metadata (knowledge_type, source_type, etc.)
            max_tags: Maximum number of tags to generate (default: 5)

        Returns:
            List of generated tags
        """
        try:
            # Prepare context for AI
            metadata_context = ""
            if existing_metadata:
                knowledge_type = existing_metadata.get("knowledge_type", "")
                source_type = existing_metadata.get("source_type", "")
                if knowledge_type:
                    metadata_context += f"Knowledge type: {knowledge_type}\n"
                if source_type:
                    metadata_context += f"Source type: {source_type}\n"

            # Create prompt for tag generation
            prompt = f"""Analyze this content and generate {max_tags} relevant tags.

{metadata_context}
Title: {title or "N/A"}

Content preview:
{content[:2000]}...

Generate tags that:
1. Capture the main topics and concepts
2. Include technical terms if applicable
3. Reflect the domain or industry
4. Are specific and actionable
5. Use lowercase and hyphens (e.g., "project-management", "electrical-engineering")

Return ONLY a JSON array of tags, nothing else.
Example: ["tag1", "tag2", "tag3"]"""

            # Call OpenAI for tag generation
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at content categorization and tagging. Generate concise, relevant tags.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            # Parse response
            tags_text = response.choices[0].message.content.strip()

            # Extract JSON array from response
            if tags_text.startswith("[") and tags_text.endswith("]"):
                tags = json.loads(tags_text)
            else:
                # Try to find JSON array in response
                import re

                json_match = re.search(r"\[.*\]", tags_text, re.DOTALL)
                if json_match:
                    tags = json.loads(json_match.group())
                else:
                    logger.warning(f"Could not parse tags from response: {tags_text}")
                    return []

            # Clean and validate tags
            cleaned_tags = []
            for tag in tags:
                if isinstance(tag, str):
                    # Clean tag: lowercase, strip whitespace, replace spaces with hyphens
                    clean_tag = tag.lower().strip().replace(" ", "-")
                    if clean_tag and len(clean_tag) <= 50:  # Max 50 chars per tag
                        cleaned_tags.append(clean_tag)

            logger.info(f"Generated {len(cleaned_tags)} tags for content")
            return cleaned_tags[:max_tags]

        except Exception as e:
            logger.error(f"Failed to generate tags: {e}")
            return []

    async def tag_knowledge_item(
        self,
        source_id: str,
        force: bool = False,
        max_tags: int = 5,
    ) -> tuple[bool, list[str]]:
        """
        Generate and apply tags to a knowledge item.

        Args:
            source_id: The source_id of the knowledge item
            force: If True, regenerate tags even if they already exist
            max_tags: Maximum number of tags to generate

        Returns:
            Tuple of (success, tags_list)
        """
        try:
            # Fetch the source
            response = self.supabase.table("archon_sources").select("*").eq("source_id", source_id).execute()

            if not response.data:
                logger.error(f"Source not found: {source_id}")
                return False, []

            source = response.data[0]
            metadata = source.get("metadata", {})
            existing_tags = metadata.get("tags", [])

            # Skip if already tagged (unless force=True)
            if existing_tags and not force:
                logger.info(f"Source {source_id} already has tags, skipping")
                return True, existing_tags

            # Use summary field for content analysis
            content = source.get("summary", "")

            if not content:
                logger.warning(f"No summary available for tagging: {source_id}")
                return False, []

            # Generate tags
            title = source.get("title", "") or source.get("source_display_name", "")
            tags = await self.generate_tags(
                content=content,
                title=title,
                existing_metadata=metadata,
                max_tags=max_tags,
            )

            if not tags:
                logger.warning(f"No tags generated for: {source_id}")
                return False, []

            # Update source with tags
            metadata["tags"] = tags
            metadata["auto_tagged"] = True

            update_response = (
                self.supabase.table("archon_sources")
                .update({"metadata": metadata})
                .eq("source_id", source_id)
                .execute()
            )

            if update_response.data:
                logger.info(f"Tagged {source_id} with: {tags}")
                return True, tags
            else:
                logger.error(f"Failed to update tags for {source_id}")
                return False, []

        except Exception as e:
            import traceback
            logger.error(f"Failed to tag knowledge item {source_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, []

    async def batch_tag_items(
        self,
        source_ids: list[str] | None = None,
        knowledge_type: str | None = None,
        force: bool = False,
        max_items: int | None = None,
    ) -> dict[str, Any]:
        """
        Tag multiple knowledge items in batch.

        Args:
            source_ids: Optional list of specific source_ids to tag
            knowledge_type: Optional filter by knowledge_type
            force: If True, regenerate tags even if they exist
            max_items: Optional limit on number of items to process

        Returns:
            Dict with stats: {total, success, failed, tags_generated}
        """
        stats = {"total": 0, "success": 0, "failed": 0, "tags_generated": 0}

        try:
            # Build query
            if source_ids:
                # Tag specific items
                items_to_tag = source_ids
            else:
                # Query items that need tagging
                query = self.supabase.table("archon_sources").select("source_id, metadata")

                if knowledge_type:
                    query = query.eq("metadata->>knowledge_type", knowledge_type)

                if not force:
                    # Only get items without tags
                    query = query.is_("metadata->>tags", "null")

                if max_items:
                    query = query.limit(max_items)

                response = query.execute()
                items_to_tag = [item["source_id"] for item in response.data]

            stats["total"] = len(items_to_tag)
            logger.info(f"Starting batch tagging for {stats['total']} items")

            # Process each item
            for source_id in items_to_tag:
                success, tags = await self.tag_knowledge_item(source_id, force=force)

                if success:
                    stats["success"] += 1
                    stats["tags_generated"] += len(tags)
                else:
                    stats["failed"] += 1

            logger.info(
                f"Batch tagging complete: {stats['success']} success, {stats['failed']} failed, "
                f"{stats['tags_generated']} tags generated"
            )
            return stats

        except Exception as e:
            logger.error(f"Batch tagging failed: {e}")
            return stats

    async def get_all_tags(self) -> dict[str, int]:
        """
        Get all tags and their usage counts across the knowledge base.

        Returns:
            Dict mapping tag names to usage counts
        """
        try:
            # Query all sources with tags
            response = (
                self.supabase.table("archon_sources").select("metadata").not_.is_("metadata->>tags", "null").execute()
            )

            # Count tag usage
            tag_counts = {}
            for item in response.data:
                tags = item.get("metadata", {}).get("tags", [])
                for tag in tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            return tag_counts

        except Exception as e:
            logger.error(f"Failed to get all tags: {e}")
            return {}
