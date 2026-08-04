import json
from pathlib import Path

from tools.agent.common import load_project_context
from tools.agent.run_ai_review import REVIEW_ROOT, load_prompt_bundle


def test_ai_review_prompt_bundle_loads_from_current_context():
    repo_root = Path(__file__).resolve().parents[3]
    context = load_project_context(repo_root / 'docs' / 'project' / 'context-summary.yaml')

    bundle = load_prompt_bundle(context)

    assert 'behavioral regressions' in bundle
    assert 'workflow and governance contract violations' in bundle


def test_ai_review_schema_file_exists_and_is_valid_json():
    schema = json.loads((REVIEW_ROOT / 'review-report.schema.json').read_text(encoding='utf-8'))

    assert schema['type'] == 'object'
    assert 'findings' in schema['properties']
