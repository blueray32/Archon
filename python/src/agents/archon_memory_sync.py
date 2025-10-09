"""
Archon Memory Sync - Syncs Obsidian vault index into Archon's database.

Stores vault metadata, notes, and tags for RAG retrieval and cross-referencing.
"""

import json
import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from .obsidian_tools import VaultIndex

logger = logging.getLogger(__name__)


class ArchonMemoryDocument(BaseModel):
    """Document to store in Archon memory."""

    content: str
    metadata: dict[str, Any]
    source_type: str = "obsidian_note"
    embedding: list[float] | None = None


class ArchonMemorySync:
    """
    Sync Obsidian vault data into Archon's memory system.

    Stores:
    - Vault index as a searchable document
    - Individual note summaries
    - Tag mappings
    """

    def __init__(self, supabase_client, embedding_service: Any | None = None):
        """
        Initialize memory sync.

        Args:
            supabase_client: Supabase client for database access
            embedding_service: Optional service for creating embeddings
        """
        self.supabase = supabase_client
        self.embedding_service = embedding_service

    async def sync_vault_index(self, vault_index: VaultIndex, create_embeddings: bool = False) -> dict[str, Any]:
        """
        Sync vault index to Archon memory.

        Args:
            vault_index: VaultIndex to sync
            create_embeddings: Whether to create embeddings for notes

        Returns:
            Sync report with statistics
        """
        logger.info(f"Syncing vault index: {vault_index.vault_path}")

        synced_notes = 0
        failed_notes = 0
        created_embeddings = 0

        # Store vault-level index
        vault_doc = self._create_vault_index_document(vault_index)
        try:
            await self._store_document(vault_doc, "obsidian_vault_index")
            logger.info("Stored vault index document")
        except Exception as e:
            logger.error(f"Failed to store vault index: {e}")

        # Store individual notes
        for note in vault_index.notes:
            try:
                note_doc = self._create_note_document(note, vault_index.vault_path)

                # Create embedding if requested
                if create_embeddings and self.embedding_service:
                    try:
                        embedding = await self.embedding_service.create_embedding(note_doc.content)
                        note_doc.embedding = embedding
                        created_embeddings += 1
                    except Exception as e:
                        logger.warning(f"Failed to create embedding for {note.path}: {e}")

                await self._store_document(note_doc, "obsidian_note")
                synced_notes += 1

            except Exception as e:
                logger.error(f"Failed to sync note {note.path}: {e}")
                failed_notes += 1

        # Store tag index
        try:
            tag_doc = self._create_tag_index_document(vault_index)
            await self._store_document(tag_doc, "obsidian_tag_index")
            logger.info("Stored tag index document")
        except Exception as e:
            logger.error(f"Failed to store tag index: {e}")

        report = {
            "vault_path": vault_index.vault_path,
            "synced_at": datetime.now().isoformat(),
            "total_notes": vault_index.notes_count,
            "synced_notes": synced_notes,
            "failed_notes": failed_notes,
            "created_embeddings": created_embeddings,
            "tags_count": len(vault_index.tags_summary),
            "areas_count": len(vault_index.areas_summary),
        }

        logger.info(f"Vault sync complete: {synced_notes}/{vault_index.notes_count} notes synced")
        return report

    def _create_vault_index_document(self, vault_index: VaultIndex) -> ArchonMemoryDocument:
        """Create a document representing the entire vault index."""
        content = f"""Obsidian Vault Index

Vault: {vault_index.vault_path}
Notes: {vault_index.notes_count}
Total Size: {vault_index.total_size_bytes / 1024:.1f} KB
Scanned: {vault_index.scanned_at}

Areas:
{self._format_summary(vault_index.areas_summary)}

Top Tags:
{self._format_summary(vault_index.tags_summary, limit=30)}
"""

        metadata = {
            "type": "vault_index",
            "vault_path": vault_index.vault_path,
            # Stable synthetic path for vault index document
            "path": f"{vault_index.vault_path}/.archon/vault_index",
            "notes_count": vault_index.notes_count,
            "total_size_bytes": vault_index.total_size_bytes,
            "scanned_at": vault_index.scanned_at,
            "areas": list(vault_index.areas_summary.keys()),
            "tags": list(vault_index.tags_summary.keys()),
        }

        return ArchonMemoryDocument(content=content, metadata=metadata, source_type="obsidian_vault_index")

    def _create_note_document(self, note: Any, vault_path: str) -> ArchonMemoryDocument:
        """Create a document for a single note."""
        content = f"""Note: {note.title}

Path: {note.path}
Tags: {', '.join(note.tags)}
Headings: {', '.join(note.headings)}

Word Count: {note.word_count}
Modified: {note.modified}
"""

        metadata = {
            "type": "note",
            "vault_path": vault_path,
            "note_path": note.path,
            # Explicit path for DB storage
            "path": note.path,
            "title": note.title,
            "tags": note.tags,
            "headings": note.headings,
            "word_count": note.word_count,
            "modified": note.modified,
            "size_bytes": note.size_bytes,
            "frontmatter": note.frontmatter,
        }

        return ArchonMemoryDocument(content=content, metadata=metadata, source_type="obsidian_note")

    def _create_tag_index_document(self, vault_index: VaultIndex) -> ArchonMemoryDocument:
        """Create a document for tag index."""
        content = f"""Obsidian Tag Index

Vault: {vault_index.vault_path}

Tag Distribution:
{self._format_summary(vault_index.tags_summary, limit=50)}

Area Distribution:
{self._format_summary(vault_index.areas_summary)}
"""

        metadata = {
            "type": "tag_index",
            "vault_path": vault_index.vault_path,
            # Stable synthetic path for tag index document
            "path": f"{vault_index.vault_path}/.archon/tag_index",
            "tags_summary": vault_index.tags_summary,
            "areas_summary": vault_index.areas_summary,
        }

        return ArchonMemoryDocument(content=content, metadata=metadata, source_type="obsidian_tag_index")

    def _format_summary(self, summary: dict[str, int], limit: int = 20) -> str:
        """Format a summary dictionary for display."""
        lines = []
        for key, count in sorted(summary.items(), key=lambda x: x[1], reverse=True)[:limit]:
            lines.append(f"  - {key}: {count}")
        return "\n".join(lines)

    async def _store_document(self, doc: ArchonMemoryDocument, kind: str) -> None:
        """
        Store a document in Archon's database.

        Args:
            doc: Document to store
            kind: Document kind (obsidian_note, obsidian_vault_index, etc.)
        """
        # Store in prp_docs table (or similar)
        try:
            path = (doc.metadata or {}).get("path")
            if not path:
                raise ValueError("Document metadata missing 'path' - refusing to insert")

            title = (doc.metadata or {}).get("title")

            metadata_for_db = dict(doc.metadata or {})
            metadata_for_db.setdefault("original_kind", kind)

            data = {
                # PRP schema allows only ('prp','doc','persona')
                "kind": "doc",
                "path": path,
                "content": doc.content,
                "metadata": metadata_for_db,
                "source_type": doc.source_type,
                "created_at": datetime.now().isoformat(),
            }

            if title:
                data["title"] = title

            if doc.embedding:
                data["embedding"] = doc.embedding

            result = self.supabase.table("prp_docs").upsert(data, on_conflict="kind,path").execute()

            if not result.data:
                raise Exception("No data returned from upsert")

        except Exception as e:
            logger.error(f"Failed to store document in database: {e}")
            raise

    async def query_vault_notes(
        self, query: str, vault_path: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Query notes from a synced vault.

        Args:
            query: Search query
            vault_path: Optional filter by vault path
            limit: Maximum results

        Returns:
            List of matching notes
        """
        try:
            # Build query
            query_builder = self.supabase.table("prp_docs").select("*").eq("source_type", "obsidian_note")

            if vault_path:
                query_builder = query_builder.eq("metadata->>vault_path", vault_path)

            # Text search (if supported)
            query_builder = query_builder.ilike("content", f"%{query}%")

            result = query_builder.limit(limit).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to query vault notes: {e}")
            return []


# Helper function for standalone sync
async def sync_obsidian_to_archon(
    vault_index: VaultIndex, supabase_client, embedding_service: Any | None = None
) -> dict[str, Any]:
    """
    Sync Obsidian vault to Archon memory.

    Args:
        vault_index: VaultIndex to sync
        supabase_client: Supabase client
        embedding_service: Optional embedding service

    Returns:
        Sync report
    """
    sync_service = ArchonMemorySync(supabase_client, embedding_service)
    return await sync_service.sync_vault_index(vault_index, create_embeddings=bool(embedding_service))
