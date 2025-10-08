"""
Obsidian Tools - Production Grade
Adds: content hashing, idempotency, frontmatter hygiene, skip rules
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from .ollama_client import OllamaClient

logger = logging.getLogger(__name__)


# File skip rules
SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".zip", ".mp4", ".mov", ".avi"}
MAX_FILE_SIZE_MB = 5


class NoteMetadata(BaseModel):
    """Metadata extracted from Obsidian note."""

    path: str
    title: str
    frontmatter: dict[str, Any] = {}
    tags: list[str] = []
    headings: list[str] = []
    word_count: int = 0
    modified: str | None = None
    size_bytes: int = 0
    content_hash: str = ""  # SHA256 of body (without frontmatter)


class VaultIndex(BaseModel):
    """Index of an Obsidian vault."""

    vault_path: str
    scanned_at: str
    notes_count: int
    total_size_bytes: int
    notes: list[NoteMetadata] = []
    tags_summary: dict[str, int] = {}
    areas_summary: dict[str, int] = {}
    skipped_files: list[str] = []
    skipped_reasons: dict[str, int] = {}


@dataclass
class TagSchema:
    """Tag schema for note classification."""

    area: list[str]
    service: list[str]
    status: list[str]
    source: list[str]


# Default tag schema
DEFAULT_TAG_SCHEMA = TagSchema(
    area=["MEP", "BIM", "Revit", "NavisWorks", "Spanish", "Community", "Engineering", "Architecture", "Construction"],
    service=["agents", "crawler", "mcp", "ui", "database", "embedding", "search"],
    status=["draft", "review", "published", "archived"],
    source=["archon", "manual", "imported", "generated"],
)


@dataclass
class SyncState:
    """State for resumable sync operations."""

    last_processed_path: str = ""
    processed_count: int = 0
    failed_paths: list[str] = None
    last_run_timestamp: str = ""
    content_hashes: dict[str, str] = None  # path -> hash

    def __post_init__(self):
        if self.failed_paths is None:
            self.failed_paths = []
        if self.content_hashes is None:
            self.content_hashes = {}

    def to_dict(self) -> dict:
        return {
            "last_processed_path": self.last_processed_path,
            "processed_count": self.processed_count,
            "failed_paths": self.failed_paths,
            "last_run_timestamp": self.last_run_timestamp,
            "content_hashes": self.content_hashes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SyncState":
        return cls(
            last_processed_path=data.get("last_processed_path", ""),
            processed_count=data.get("processed_count", 0),
            failed_paths=data.get("failed_paths", []),
            last_run_timestamp=data.get("last_run_timestamp", ""),
            content_hashes=data.get("content_hashes", {}),
        )

    def save(self, path: Path):
        """Save state to JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "SyncState":
        """Load state from JSON file."""
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls.from_dict(data)


class ObsidianToolsProduction:
    """Production-grade Obsidian tools with idempotency and resume."""

    def __init__(self, vault_path: str, tag_schema: TagSchema | None = None):
        """Initialize tools."""
        self.vault_path = Path(vault_path)
        self.tag_schema = tag_schema or DEFAULT_TAG_SCHEMA

        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {vault_path}")

    def compute_content_hash(self, body: str) -> str:
        """Compute SHA256 hash of note body (without frontmatter)."""
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def should_skip_file(self, file_path: Path) -> tuple[bool, str | None]:
        """
        Check if file should be skipped.

        Returns:
            (should_skip, reason)
        """
        # Check extension
        if file_path.suffix.lower() in SKIP_EXTENSIONS:
            return True, f"binary_extension_{file_path.suffix}"

        # Check size
        try:
            size_mb = file_path.stat().st_size / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                return True, f"too_large_{size_mb:.1f}MB"
        except Exception:
            return True, "stat_failed"

        return False, None

    def scan_vault(
        self, exclude_patterns: list[str] | None = None, state: SyncState | None = None
    ) -> tuple[VaultIndex, SyncState]:
        """
        Scan vault with skip rules and state tracking.

        Args:
            exclude_patterns: Patterns to exclude
            state: Previous sync state for resume

        Returns:
            (VaultIndex, updated_state)
        """
        exclude_patterns = exclude_patterns or [".git", ".obsidian", ".trash"]
        state = state or SyncState()

        logger.info(f"Scanning vault: {self.vault_path}")

        notes: list[NoteMetadata] = []
        skipped_files: list[str] = []
        skip_reasons: dict[str, int] = {}
        total_size = 0

        for md_file in self.vault_path.rglob("*.md"):
            # Check exclusions
            if any(pattern in str(md_file) for pattern in exclude_patterns):
                continue

            # Check skip rules
            should_skip, reason = self.should_skip_file(md_file)
            if should_skip:
                skipped_files.append(str(md_file.relative_to(self.vault_path)))
                skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
                continue

            try:
                metadata = self.extract_metadata_with_hash(md_file)
                notes.append(metadata)
                total_size += metadata.size_bytes

                # Update state
                state.content_hashes[metadata.path] = metadata.content_hash

            except Exception as e:
                logger.warning(f"Failed to process {md_file}: {e}")
                state.failed_paths.append(str(md_file.relative_to(self.vault_path)))

        # Build summaries
        tags_summary: dict[str, int] = {}
        areas_summary: dict[str, int] = {}

        for note in notes:
            for tag in note.tags:
                tags_summary[tag] = tags_summary.get(tag, 0) + 1

            area = note.frontmatter.get("area")
            if area:
                areas_summary[area] = areas_summary.get(area, 0) + 1

        index = VaultIndex(
            vault_path=str(self.vault_path),
            scanned_at=datetime.now().isoformat(),
            notes_count=len(notes),
            total_size_bytes=total_size,
            notes=notes,
            tags_summary=tags_summary,
            areas_summary=areas_summary,
            skipped_files=skipped_files,
            skipped_reasons=skip_reasons,
        )

        logger.info(
            f"Scanned {len(notes)} notes, {total_size / 1024:.1f} KB total, skipped {len(skipped_files)} files"
        )

        return index, state

    def extract_metadata_with_hash(self, note_path: Path) -> NoteMetadata:
        """Extract metadata including content hash."""
        content = note_path.read_text(encoding="utf-8")
        frontmatter, body = self.parse_frontmatter(content)

        # Compute content hash
        content_hash = self.compute_content_hash(body)

        # Extract headings
        headings = re.findall(r"^#{1,6}\s+(.+)$", body, re.MULTILINE)

        # Extract inline tags
        inline_tags = re.findall(r"#([a-zA-Z0-9_/-]+)", body)

        # Combine tags
        all_tags = set(frontmatter.get("tags", []) + inline_tags)

        # Get file stats
        stat = note_path.stat()

        return NoteMetadata(
            path=str(note_path.relative_to(self.vault_path)),
            title=frontmatter.get("title", note_path.stem),
            frontmatter=frontmatter,
            tags=sorted(list(all_tags)),
            headings=headings,
            word_count=len(body.split()),
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            size_bytes=stat.st_size,
            content_hash=content_hash,
        )

    def parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """Parse YAML frontmatter."""
        if not content.startswith("---"):
            return {}, content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content

        frontmatter_raw = parts[1].strip()
        body = parts[2].strip()

        try:
            frontmatter = yaml.safe_load(frontmatter_raw) or {}
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
            frontmatter = {}

        return frontmatter, body

    def update_frontmatter_hygiene(
        self, note_path: Path, updates: dict[str, Any], merge: bool = True, preserve_existing: bool = True
    ) -> dict[str, Any]:
        """
        Update frontmatter with hygiene rules.

        Args:
            note_path: Path to note
            updates: New values
            merge: Merge with existing
            preserve_existing: Don't overwrite existing values

        Returns:
            Change summary
        """
        content = note_path.read_text(encoding="utf-8")
        frontmatter, body = self.parse_frontmatter(content)

        old_frontmatter = frontmatter.copy()

        if merge:
            # Merge with preservation rules
            for key, value in updates.items():
                if preserve_existing and key in frontmatter and frontmatter[key]:
                    # Skip if existing value present
                    continue
                frontmatter[key] = value
        else:
            frontmatter = updates.copy()

        # Ensure required fields
        if "updated" not in frontmatter:
            frontmatter["updated"] = datetime.now().isoformat()
        else:
            frontmatter["updated"] = datetime.now().isoformat()

        if "archon_task" not in frontmatter:
            frontmatter["archon_task"] = "obsidian_sync"

        # Normalize tags
        if "tags" in frontmatter:
            if isinstance(frontmatter["tags"], str):
                frontmatter["tags"] = [frontmatter["tags"]]
            elif not isinstance(frontmatter["tags"], list):
                frontmatter["tags"] = []
        else:
            frontmatter["tags"] = []

        # Write updated content
        new_content = self._build_markdown(frontmatter, body)
        note_path.write_text(new_content, encoding="utf-8")

        # Build change summary
        changes = {}
        for key in set(list(old_frontmatter.keys()) + list(frontmatter.keys())):
            old_val = old_frontmatter.get(key)
            new_val = frontmatter.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        logger.debug(f"Updated {note_path.name}: {len(changes)} changes")
        return changes

    def _build_markdown(self, frontmatter: dict[str, Any], body: str) -> str:
        """Build markdown with frontmatter."""
        if not frontmatter:
            return body

        yaml_content = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_content}---\n\n{body}"

    def has_content_changed(self, note_path: str, state: SyncState) -> bool:
        """Check if note content changed since last run."""
        if note_path not in state.content_hashes:
            return True  # New note

        full_path = self.vault_path / note_path
        if not full_path.exists():
            return False  # Deleted

        content = full_path.read_text(encoding="utf-8")
        _, body = self.parse_frontmatter(content)
        current_hash = self.compute_content_hash(body)

        return current_hash != state.content_hashes[note_path]

    async def auto_tag_notes_with_resume(
        self,
        notes: list[NoteMetadata],
        ollama_client: OllamaClient,
        model: str,
        state: SyncState,
        max_concurrent: int = 5,
    ) -> tuple[dict[str, dict[str, Any]], SyncState]:
        """
        Auto-tag notes with idempotency and resume.

        Only processes notes that:
        1. Have changed since last run
        2. Haven't been processed yet in this run
        """
        suggestions = {}
        notes_to_process = []

        # Filter to only changed notes
        for note in notes:
            if self.has_content_changed(note.path, state):
                notes_to_process.append(note)
            else:
                logger.debug(f"Skipping unchanged note: {note.path}")

        logger.info(f"Processing {len(notes_to_process)}/{len(notes)} notes (rest unchanged)")

        if not notes_to_process:
            return {}, state

        # Build system prompt
        system_prompt = f"""You are a document tagger. Given a note's title, headings, and existing tags, suggest:
- area: One of {', '.join(self.tag_schema.area)}
- service: One of {', '.join(self.tag_schema.service)} (if applicable, can be empty)
- status: One of {', '.join(self.tag_schema.status)}

Respond with JSON only: {{"area": "...", "service": "...", "status": "..."}}
Leave service empty ("") if not applicable."""

        # Build prompts
        prompts = []
        for note in notes_to_process:
            prompt = f"""Title: {note.title}
Headings: {', '.join(note.headings[:5])}
Existing tags: {', '.join(note.tags[:10])}

Suggest tags:"""
            prompts.append(prompt)

        # Batch process
        results = await ollama_client.batch_generate(
            model=model, prompts=prompts, system=system_prompt, max_concurrent=max_concurrent
        )

        for note, result in zip(notes_to_process, results):
            try:
                tags = json.loads(result)
                suggestions[note.path] = tags
                state.processed_count += 1
                state.last_processed_path = note.path
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tags for {note.path}")
                state.failed_paths.append(note.path)

        return suggestions, state

    def create_index_note(self, index: VaultIndex, output_path: Path | None = None) -> Path:
        """Create index note (MOC)."""
        if output_path is None:
            output_path = self.vault_path / "Archon" / "index.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        frontmatter = {
            "title": "Archon Vault Index",
            "source": "archon",
            "generated_at": index.scanned_at,
            "notes_count": index.notes_count,
            "tags": ["archon", "index", "moc"],
        }

        body_lines = [
            "# Archon Vault Index",
            "",
            f"**Generated:** {index.scanned_at}  ",
            f"**Notes:** {index.notes_count}  ",
            f"**Total Size:** {index.total_size_bytes / 1024:.1f} KB",
            "",
        ]

        # Add skip summary if any
        if index.skipped_files:
            body_lines.extend(
                [
                    "## Skipped Files",
                    "",
                    f"**Total Skipped:** {len(index.skipped_files)}",
                    "",
                    "**Reasons:**",
                    "",
                ]
            )
            for reason, count in sorted(index.skipped_reasons.items(), key=lambda x: x[1], reverse=True):
                body_lines.append(f"- {reason}: {count}")
            body_lines.append("")

        body_lines.extend(["## Areas", ""])
        for area, count in sorted(index.areas_summary.items(), key=lambda x: x[1], reverse=True):
            body_lines.append(f"- **{area}**: {count} notes")

        body_lines.extend(["", "## Tags", ""])
        for tag, count in sorted(index.tags_summary.items(), key=lambda x: x[1], reverse=True)[:20]:
            body_lines.append(f"- #{tag} ({count})")

        body_lines.extend(["", "## Recent Notes", ""])
        recent_notes = sorted(index.notes, key=lambda n: n.modified or "", reverse=True)[:20]
        for note in recent_notes:
            body_lines.append(f"- [[{note.path}|{note.title}]]")

        body = "\n".join(body_lines)
        content = self._build_markdown(frontmatter, body)

        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Created index note at {output_path}")

        return output_path
