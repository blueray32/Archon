"""
Obsidian Tools - Vault scanning, tagging, and syncing utilities.

Provides:
- Vault scanning and indexing
- Frontmatter management
- Auto-tagging with Ollama
- Archon integration
"""

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


class VaultIndex(BaseModel):
    """Index of an Obsidian vault."""

    vault_path: str
    scanned_at: str
    notes_count: int
    total_size_bytes: int
    notes: list[NoteMetadata] = []
    tags_summary: dict[str, int] = {}
    areas_summary: dict[str, int] = {}


@dataclass
class TagSchema:
    """Tag schema for note classification."""

    area: list[str]
    service: list[str]
    status: list[str]
    source: list[str]


def _normalize_tag_field(value: Any) -> list[str]:
    """Normalize frontmatter tag field into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str):
                item = item.strip()
                if item:
                    normalized.append(item)
        return normalized
    return []


# Default tag schema for Archon + Obsidian
DEFAULT_TAG_SCHEMA = TagSchema(
    area=["MEP", "BIM", "Revit", "NavisWorks", "Spanish", "Community", "Engineering", "Architecture", "Construction"],
    service=["agents", "crawler", "mcp", "ui", "database", "embedding", "search"],
    status=["draft", "review", "published", "archived"],
    source=["archon", "manual", "imported", "generated"],
)


class ObsidianTools:
    """Tools for working with Obsidian vaults."""

    def __init__(self, vault_path: str, tag_schema: TagSchema | None = None):
        """
        Initialize Obsidian tools.

        Args:
            vault_path: Path to Obsidian vault root
            tag_schema: Tag schema for classification
        """
        self.vault_path = Path(vault_path)
        self.tag_schema = tag_schema or DEFAULT_TAG_SCHEMA

        if not self.vault_path.exists():
            raise ValueError(f"Vault path does not exist: {vault_path}")

    def scan_vault(self, exclude_patterns: list[str] | None = None) -> VaultIndex:
        """
        Scan the entire vault and build an index.

        Args:
            exclude_patterns: Glob patterns to exclude (e.g., [".git", ".obsidian"])

        Returns:
            VaultIndex with all notes
        """
        exclude_patterns = exclude_patterns or [".git", ".obsidian", ".trash"]
        logger.info(f"Scanning vault: {self.vault_path}")

        notes: list[NoteMetadata] = []
        total_size = 0

        for md_file in self.vault_path.rglob("*.md"):
            # Check exclusions
            if any(pattern in str(md_file) for pattern in exclude_patterns):
                continue

            try:
                metadata = self.extract_metadata(md_file)
                notes.append(metadata)
                total_size += metadata.size_bytes
            except Exception as e:
                logger.warning(f"Failed to process {md_file}: {e}")

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
        )

        logger.info(f"Scanned {len(notes)} notes, {total_size / 1024:.1f} KB total")
        return index

    def extract_metadata(self, note_path: Path) -> NoteMetadata:
        """
        Extract metadata from a single note.

        Args:
            note_path: Path to markdown file

        Returns:
            NoteMetadata with extracted information
        """
        content = note_path.read_text(encoding="utf-8")
        frontmatter, body = self.parse_frontmatter(content)

        # Extract headings
        headings = re.findall(r"^#{1,6}\s+(.+)$", body, re.MULTILINE)

        # Extract inline tags
        inline_tags = re.findall(r"#([a-zA-Z0-9_/-]+)", body)

        # Combine frontmatter tags and inline tags
        frontmatter_tags = _normalize_tag_field(frontmatter.get("tags"))
        all_tags = set(frontmatter_tags + inline_tags)

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
        )

    def parse_frontmatter(self, content: str) -> tuple[dict[str, Any], str]:
        """
        Parse YAML frontmatter from markdown content.

        Args:
            content: Markdown file content

        Returns:
            Tuple of (frontmatter_dict, body_content)
        """
        # Check for YAML frontmatter
        if not content.startswith("---"):
            return {}, content

        # Find end of frontmatter
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

    def update_frontmatter(self, note_path: Path, updates: dict[str, Any], merge: bool = True) -> None:
        """
        Update frontmatter in a note.

        Args:
            note_path: Path to markdown file
            updates: Dictionary of frontmatter fields to update
            merge: If True, merge with existing frontmatter; if False, replace
        """
        content = note_path.read_text(encoding="utf-8")
        frontmatter, body = self.parse_frontmatter(content)

        if merge:
            frontmatter.update(updates)
        else:
            frontmatter = updates

        # Add/update timestamp
        frontmatter["updated"] = datetime.now().isoformat()

        # Write updated content
        new_content = self._build_markdown(frontmatter, body)
        note_path.write_text(new_content, encoding="utf-8")

        logger.debug(f"Updated frontmatter in {note_path}")

    def _build_markdown(self, frontmatter: dict[str, Any], body: str) -> str:
        """Build markdown content from frontmatter and body."""
        if not frontmatter:
            return body

        yaml_content = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_content}---\n\n{body}"

    async def auto_tag_notes(
        self, notes: list[NoteMetadata], ollama_client: OllamaClient, model: str = "qwen2.5:3b"
    ) -> dict[str, dict[str, Any]]:
        """
        Auto-tag notes using Ollama.

        Args:
            notes: List of notes to tag
            ollama_client: Ollama client instance
            model: Model to use for tagging

        Returns:
            Dictionary mapping note paths to suggested tags
        """
        suggestions = {}

        system_prompt = f"""You are a document tagger. Given a note's title, headings, and existing tags, suggest:
- area: One of {', '.join(self.tag_schema.area)}
- service: One of {', '.join(self.tag_schema.service)} (if applicable)
- status: One of {', '.join(self.tag_schema.status)}

Respond with JSON only: {{"area": "...", "service": "...", "status": "..."}}
"""

        prompts = []
        for note in notes:
            prompt = f"""Title: {note.title}
Headings: {', '.join(note.headings[:5])}
Existing tags: {', '.join(note.tags[:10])}

Suggest tags:"""
            prompts.append(prompt)

        # Batch process
        results = await ollama_client.batch_generate(model=model, prompts=prompts, system=system_prompt)

        for note, result in zip(notes, results):
            try:
                tags = json.loads(result)
                suggestions[note.path] = tags
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tags for {note.path}")
                suggestions[note.path] = {}

        return suggestions

    def create_index_note(self, index: VaultIndex, output_path: Path | None = None) -> Path:
        """
        Create a master index note (MOC) for the vault.

        Args:
            index: VaultIndex to summarize
            output_path: Optional custom output path

        Returns:
            Path to created index note
        """
        if output_path is None:
            output_path = self.vault_path / "Archon" / "index.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build index content
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
            "## Areas",
            "",
        ]

        for area, count in sorted(index.areas_summary.items(), key=lambda x: x[1], reverse=True):
            body_lines.append(f"- **{area}**: {count} notes")

        body_lines.extend(["", "## Tags", ""])

        for tag, count in sorted(index.tags_summary.items(), key=lambda x: x[1], reverse=True)[:20]:
            body_lines.append(f"- #{tag} ({count})")

        body_lines.extend(["", "## Recent Notes", ""])

        # Sort by modified time
        recent_notes = sorted(index.notes, key=lambda n: n.modified or "", reverse=True)[:20]
        for note in recent_notes:
            title = note.title
            path = note.path
            body_lines.append(f"- [[{path}|{title}]]")

        body = "\n".join(body_lines)
        content = self._build_markdown(frontmatter, body)

        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Created index note at {output_path}")

        return output_path


# Helper functions
def scan_obsidian_vault(vault_path: str) -> VaultIndex:
    """
    Quick helper to scan an Obsidian vault.

    Args:
        vault_path: Path to vault root

    Returns:
        VaultIndex with all notes
    """
    tools = ObsidianTools(vault_path)
    return tools.scan_vault()


async def auto_tag_vault(
    vault_path: str, ollama_host: str = "http://localhost:11434", model: str = "qwen2.5:3b"
) -> dict[str, dict[str, Any]]:
    """
    Auto-tag all notes in a vault.

    Args:
        vault_path: Path to vault root
        ollama_host: Ollama API endpoint
        model: Model to use for tagging

    Returns:
        Dictionary of suggested tags per note
    """
    tools = ObsidianTools(vault_path)
    index = tools.scan_vault()

    async with OllamaClient(base_url=ollama_host) as client:
        suggestions = await tools.auto_tag_notes(index.notes, client, model)

    return suggestions
