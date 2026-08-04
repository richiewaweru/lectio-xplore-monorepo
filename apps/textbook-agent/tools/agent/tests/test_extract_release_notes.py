from pathlib import Path

from tools.agent.extract_release_notes import extract_release_notes


def test_extract_release_notes_reads_current_changelog_section():
    repo_root = Path(__file__).resolve().parents[3]
    context_path = repo_root / 'docs' / 'project' / 'context-summary.yaml'

    notes = extract_release_notes(context_path=context_path, version='v0.1.0', repo_root=repo_root)

    assert notes.startswith('## [0.1.0]')
