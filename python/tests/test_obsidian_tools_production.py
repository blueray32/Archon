import textwrap
from pathlib import Path

from src.agents.obsidian_tools_production import ObsidianToolsProduction, SyncState


def test_has_content_changed_respects_saved_hash(tmp_path: Path):
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    note = vault_root / "note.md"
    note.write_text(
        textwrap.dedent(
            """\
            ---
            title: Sample
            ---

            # Heading
            Body text here.
            """
        ),
        encoding="utf-8",
    )

    tools = ObsidianToolsProduction(str(vault_root))
    state = SyncState()

    index, state = tools.scan_vault(state=state)
    assert index.notes_count == 1
    assert state.pending_hashes

    state.content_hashes = dict(state.pending_hashes)
    state.pending_hashes = {}

    note_path = index.notes[0].path
    assert tools.has_content_changed(note_path, state) is False

    note.write_text(
        textwrap.dedent(
            """\
            ---
            title: Sample
            ---

            # Heading
            Body text changed.
            """
        ),
        encoding="utf-8",
    )

    assert tools.has_content_changed(note_path, state) is True
