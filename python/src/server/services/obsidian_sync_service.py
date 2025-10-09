"""
Obsidian Vault Sync Service

This service provides bidirectional synchronization between Obsidian vaults and Archon's knowledge base.
It watches for file changes, parses Obsidian-specific syntax (frontmatter, tags, links), and maintains
a live sync between your Obsidian vault and Archon's RAG system.
"""

import asyncio
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Make watchdog optional for now
try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    FileSystemEventHandler = object  # Dummy class
    Observer = None

from ..config.logfire_config import get_logger
from ..services.storage import DocumentStorageService
from ..services.source_management_service import SourceManagementService
from ..utils import get_supabase_client

logger = get_logger(__name__)


class ObsidianVaultSyncService:
    """Service for syncing Obsidian vaults with Archon knowledge base."""

    def __init__(self, vault_path: str):
        """
        Initialize the Obsidian sync service.

        Args:
            vault_path: Path to the Obsidian vault directory
        """
        self.vault_path = Path(vault_path)
        self.supabase = get_supabase_client()
        self.storage_service = DocumentStorageService(self.supabase)
        self.source_service = SourceManagementService(self.supabase)
        self.observer = None
        self.is_watching = False
        self.loop: asyncio.AbstractEventLoop | None = None

        # Track synced files and their hashes to detect changes
        self.synced_files: dict[str, str] = {}  # path -> hash

        logger.info(f"Initialized Obsidian sync service for vault: {vault_path}")

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """
        Parse YAML frontmatter from markdown content.

        Args:
            content: Raw markdown content

        Returns:
            Tuple of (frontmatter_dict, content_without_frontmatter)
        """
        frontmatter = {}
        body = content

        # Check for YAML frontmatter (--- ... ---)
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except yaml.YAMLError as e:
                    logger.warning(f"Failed to parse frontmatter: {e}")

        return frontmatter, body

    def _extract_obsidian_tags(self, content: str) -> list[str]:
        """
        Extract Obsidian tags from content (#tag format).

        Args:
            content: Markdown content

        Returns:
            List of tags
        """
        # Match #tag format (but not in code blocks or headings at start of line)
        tag_pattern = r"(?<!^)(?<!#)#([a-zA-Z][a-zA-Z0-9/_-]*)"
        tags = re.findall(tag_pattern, content, re.MULTILINE)
        return list(set(tags))  # Remove duplicates

    def _extract_obsidian_links(self, content: str) -> list[str]:
        """
        Extract Obsidian wiki links [[link]] from content.

        Args:
            content: Markdown content

        Returns:
            List of linked note names
        """
        # Match [[link]] or [[link|display text]]
        link_pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
        links = re.findall(link_pattern, content)
        return links

    def _compute_file_hash(self, file_path: Path) -> str:
        """
        Compute MD5 hash of file content.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash string
        """
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def _get_relative_path(self, file_path: Path) -> str:
        """
        Get path relative to vault root.

        Args:
            file_path: Absolute file path

        Returns:
            Relative path string
        """
        return str(file_path.relative_to(self.vault_path))

    async def index_file(self, file_path: Path, knowledge_type: str = "technical") -> bool:
        """
        Index a single Obsidian file into the knowledge base.

        Args:
            file_path: Path to the markdown file
            knowledge_type: Knowledge type classification

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse frontmatter
            frontmatter, body = self._parse_frontmatter(content)

            # Extract Obsidian-specific elements
            inline_tags = self._extract_obsidian_tags(body)
            links = self._extract_obsidian_links(body)

            # Combine frontmatter tags with inline tags
            frontmatter_tags = frontmatter.get("tags", [])
            if isinstance(frontmatter_tags, str):
                frontmatter_tags = [frontmatter_tags]
            all_tags = list(set(frontmatter_tags + inline_tags))

            # Generate source_id from relative path
            relative_path = self._get_relative_path(file_path)
            source_id = f"obsidian_{relative_path.replace('/', '_').replace('.md', '')}"

            # Prepare metadata
            metadata = {
                "source_type": "file",
                "file_name": file_path.name,
                "file_type": "markdown",
                "obsidian_vault": True,
                "vault_path": str(self.vault_path),
                "relative_path": relative_path,
                "obsidian_links": links,
                **frontmatter,  # Include all frontmatter
            }
            frontmatter_overrides = {
                "obsidian_vault": True,
                "vault_path": str(self.vault_path),
                "relative_path": relative_path,
                "area": frontmatter.get("area"),
                "service": frontmatter.get("service"),
                "status": frontmatter.get("status"),
            }
            frontmatter_overrides = {k: v for k, v in frontmatter_overrides.items() if v is not None and v != ""}
            frontmatter_overrides.setdefault("obsidian_vault", True)
            frontmatter_overrides.setdefault("vault_path", str(self.vault_path))
            frontmatter_overrides.setdefault("relative_path", relative_path)

            # Use existing storage service to process the file
            # This handles chunking, embeddings, and database storage
            success, result = await self.storage_service.upload_document(
                file_content=body,  # Use the body without frontmatter
                filename=file_path.name,
                source_id=source_id,
                knowledge_type=knowledge_type,
                tags=all_tags,
                metadata_overrides=frontmatter_overrides,
            )

            if not success:
                raise Exception(f"Upload failed: {result.get('error', 'Unknown error')}")

            # Track synced file
            file_hash = self._compute_file_hash(file_path)
            self.synced_files[relative_path] = file_hash

            logger.info(f"Indexed Obsidian file: {relative_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to index Obsidian file {file_path}: {e}")
            return False

    async def _remove_indexed_file(self, relative_path: str) -> None:
        """Remove indexed records for a deleted Obsidian note."""
        source_id = f"obsidian_{relative_path.replace('/', '_').replace('.md', '')}"
        try:
            loop = asyncio.get_running_loop()
            success, result = await loop.run_in_executor(
                None, self.source_service.delete_source, source_id
            )
            if not success:
                logger.warning(f"Failed to delete source for {relative_path}: {result.get('error')}")
            else:
                logger.info(f"Removed indexed records for {relative_path}")
        except RuntimeError:
            # Fallback if no running loop (should not happen when called via schedule)
            success, result = self.source_service.delete_source(source_id)
            if not success:
                logger.warning(f"Failed to delete source for {relative_path}: {result.get('error')}")
            else:
                logger.info(f"Removed indexed records for {relative_path}")

    async def index_vault(
        self, knowledge_type: str = "technical", exclude_patterns: list[str] | None = None, max_files: int | None = None
    ) -> dict[str, int]:
        """
        Index entire Obsidian vault into knowledge base.

        Args:
            knowledge_type: Default knowledge type for all files
            exclude_patterns: List of glob patterns to exclude (e.g., [".obsidian/*", "templates/*"])
            max_files: Maximum number of files to index (for testing)

        Returns:
            Dict with stats: {"total": int, "success": int, "failed": int}
        """
        logger.info(f"Starting full vault indexing: {self.vault_path}")

        exclude_patterns = exclude_patterns or [
            ".obsidian/*",
            ".trash/*",
            "node_modules/*",
        ]

        stats = {"total": 0, "success": 0, "failed": 0}

        # Find all markdown files
        md_files = list(self.vault_path.rglob("*.md"))

        # Filter excluded patterns
        filtered_files = []
        for md_file in md_files:
            relative_path = self._get_relative_path(md_file)
            excluded = any(
                Path(relative_path).match(pattern) for pattern in exclude_patterns
            )
            if not excluded:
                filtered_files.append(md_file)

        # Limit files if max_files specified (for testing)
        if max_files and max_files > 0:
            filtered_files = filtered_files[:max_files]
            logger.info(f"Limiting to first {max_files} files for testing")

        stats["total"] = len(filtered_files)
        logger.info(f"Found {stats['total']} markdown files to index")

        # Index files in batches to avoid overwhelming the system
        batch_size = 10
        for i in range(0, len(filtered_files), batch_size):
            batch = filtered_files[i : i + batch_size]

            # Process batch concurrently
            tasks = [self.index_file(file_path, knowledge_type) for file_path in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successes/failures
            for result in results:
                if isinstance(result, bool) and result:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1

            logger.info(
                f"Batch {i // batch_size + 1}: {stats['success']}/{stats['total']} indexed"
            )

            # Small delay between batches to avoid rate limits
            await asyncio.sleep(0.5)

        logger.info(
            f"Vault indexing complete: {stats['success']} success, {stats['failed']} failed"
        )
        return stats

    def start_watching(self, knowledge_type: str = "technical") -> None:
        """
        Start watching vault for file changes and auto-sync.

        Args:
            knowledge_type: Default knowledge type for new/modified files
        """
        if not WATCHDOG_AVAILABLE:
            raise Exception("Watchdog library not installed. File watching is not available.")

        if self.is_watching:
            logger.warning("Vault watching already started")
            return

        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise RuntimeError("Vault watching requires an active asyncio event loop") from exc

        class ObsidianFileHandler(FileSystemEventHandler):
            """Handler for Obsidian file system events."""

            def __init__(self, sync_service: ObsidianVaultSyncService):
                self.sync_service = sync_service
                self.knowledge_type = knowledge_type

            def on_modified(self, event):
                if event.is_directory or not event.src_path.endswith(".md"):
                    return
                file_path = Path(event.src_path)
                logger.info(f"File modified: {file_path}")
                self.sync_service._submit_async(self.sync_service.index_file(file_path, self.knowledge_type))

            def on_created(self, event):
                if event.is_directory or not event.src_path.endswith(".md"):
                    return
                file_path = Path(event.src_path)
                logger.info(f"File created: {file_path}")
                self.sync_service._submit_async(self.sync_service.index_file(file_path, self.knowledge_type))

            def on_deleted(self, event):
                if event.is_directory or not event.src_path.endswith(".md"):
                    return
                file_path = Path(event.src_path)
                relative_path = str(file_path.relative_to(self.sync_service.vault_path))
                logger.info(f"File deleted: {relative_path}")
                self.sync_service._submit_async(self.sync_service._handle_file_deleted(relative_path))

        event_handler = ObsidianFileHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.vault_path), recursive=True)
        self.observer.start()
        self.is_watching = True

        logger.info(f"Started watching Obsidian vault: {self.vault_path}")

    def stop_watching(self) -> None:
        """Stop watching vault for changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.is_watching = False
            logger.info("Stopped watching Obsidian vault")
        self.loop = None

    def _submit_async(self, coro: Any) -> None:
        """Submit coroutine to stored event loop safely."""
        if self.loop is None:
            logger.warning("Async submission requested without event loop; dropping task")
            return
        future = asyncio.run_coroutine_threadsafe(self._wrap_coro(coro), self.loop)
        future.add_done_callback(self._log_future_error)

    async def _wrap_coro(self, coro: Any) -> None:
        """Wrapper to await coroutine and suppress cancellation noise."""
        try:
            await coro
        except asyncio.CancelledError:
            logger.debug("Watcher task cancelled")
        except Exception as exc:
            logger.error(f"Watcher task failed: {exc}")

    @staticmethod
    def _log_future_error(fut: asyncio.Future) -> None:
        """Log unexpected errors from run_coroutine_threadsafe futures."""
        if fut.cancelled():
            return
        exc = fut.exception()
        if exc:
            logger.error(f"Watcher async task raised: {exc}")

    async def _handle_file_deleted(self, relative_path: str) -> None:
        """Handle removal of a vault file."""
        try:
            await self._remove_indexed_file(relative_path)
        finally:
            self.synced_files.pop(relative_path, None)
