from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from anthropic import Anthropic
from openai import OpenAI

from tools.agent.common import (
    DEFAULT_CONTEXT_PATH,
    REPO_ROOT,
    ContextError,
    load_project_context,
    resolve_repo_path,
)

REVIEW_ROOT = REPO_ROOT / 'agents' / 'prompts'
DEFAULT_OPENAI_MODEL = 'gpt-4.1-mini'
DEFAULT_ANTHROPIC_MODEL = 'claude-3-5-haiku-latest'
MAX_PATCH_CHARS = 32000


class ReviewSkip(RuntimeError):
    """Raised when AI review should exit cleanly without producing a failure."""


class ReviewError(RuntimeError):
    """Raised when AI review cannot complete successfully."""


def load_text(path: Path) -> str:
    return path.read_text(encoding='utf-8').strip()


def github_request(url: str, token: str, user_agent: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': user_agent,
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode('utf-8'))


def github_post(url: str, token: str, payload: dict[str, Any], user_agent: str) -> None:
    request = urllib.request.Request(
        url,
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': user_agent,
            'Content-Type': 'application/json',
        },
        data=json.dumps(payload).encode('utf-8'),
        method='POST',
    )
    with urllib.request.urlopen(request):
        return


def load_event(event_path: Path) -> dict[str, Any]:
    return json.loads(event_path.read_text(encoding='utf-8'))


def collect_pr_files(repository: str, pr_number: int, token: str, user_agent: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    page = 1
    while True:
        url = (
            f'https://api.github.com/repos/{repository}/pulls/{pr_number}/files'
            f'?per_page=100&page={page}'
        )
        payload = github_request(url, token, user_agent=user_agent)
        if not payload:
            break
        files.extend(payload)
        if len(payload) < 100:
            break
        page += 1
    return files


def load_prompt_bundle(context: dict[str, Any]) -> str:
    prompt_paths = context['github'].get('ai_review_prompts', [])
    chunks = []
    for prompt_path in prompt_paths:
        chunks.append(load_text(resolve_repo_path(prompt_path, repo_root=REPO_ROOT)))
    return '\n\n'.join(chunks)


def build_review_payload(
    context: dict[str, Any],
    event: dict[str, Any],
    files: list[dict[str, Any]],
) -> str:
    review_schema = load_text(REVIEW_ROOT / 'review-report.schema.json')
    prompts = load_prompt_bundle(context)
    local_docs = context['docs'].get('local_context_docs', [])
    doc_listing = '\n'.join(f'- {doc}' for doc in local_docs) or '- <none declared>'

    pr = event['pull_request']
    file_chunks: list[str] = []
    remaining = MAX_PATCH_CHARS
    for item in files:
        patch = item.get('patch', '') or '<no unified diff available>'
        snippet = (
            f"FILE: {item['filename']}\n"
            f"STATUS: {item['status']}\n"
            f"ADDITIONS: {item['additions']} DELETIONS: {item['deletions']}\n"
            f"PATCH:\n{patch}\n"
        )
        if len(snippet) > remaining:
            snippet = snippet[:remaining]
        if not snippet:
            break
        file_chunks.append(snippet)
        remaining -= len(snippet)
        if remaining <= 0:
            break

    prompt = f"""
You are an external code review agent for the repository \"{context['repo']['name']}\".

Return a single JSON object that matches this schema exactly:
{review_schema}

Review goals:
{prompts}

Project context docs that may inform your review:
{doc_listing}

Pull request metadata:
- Title: {pr.get('title', '')}
- Number: {pr.get('number')}
- Author: {pr.get('user', {}).get('login', '')}
- Base branch: {pr.get('base', {}).get('ref', '')}
- Head branch: {pr.get('head', {}).get('ref', '')}

Pull request body:
{pr.get('body') or '<empty>'}

Changed files:
{chr(10).join(file_chunks) if file_chunks else '<no file changes available>'}

Constraints:
- Report only findings that are supported by the diff.
- Focus on bug risk, architectural violations, workflow contract issues, and missing or weak validation.
- Prefer fewer high-signal findings over speculative noise.
- Use severity values critical, high, medium, or low.
- Use category values bug-risk, architecture-compliance, test-gap, or workflow-compliance.
- If there are no significant issues, return an empty findings list and an overall_risk of low.
"""
    return prompt.strip()


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith('```'):
        stripped = stripped.strip('`')
        if '\n' in stripped:
            stripped = stripped.split('\n', 1)[1]
    start = stripped.find('{')
    end = stripped.rfind('}')
    if start == -1 or end == -1:
        raise ReviewError('Provider response did not contain a JSON object.')
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ReviewError(f'Provider response was not valid JSON: {exc}') from exc


def call_openai(prompt: str, api_key: str, model: str) -> dict[str, Any]:
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        temperature=0,
        max_output_tokens=1800,
        instructions='Return only JSON with no markdown fences or prose outside the object.',
        input=prompt,
    )
    return extract_json_object(response.output_text)


def call_anthropic(prompt: str, api_key: str, model: str) -> dict[str, Any]:
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        temperature=0,
        max_tokens=1800,
        system='Return only JSON with no markdown fences or commentary.',
        messages=[{'role': 'user', 'content': prompt}],
    )
    text_blocks = [
        block.text
        for block in response.content
        if getattr(block, 'type', None) == 'text'
    ]
    return extract_json_object('\n'.join(text_blocks))


def render_markdown(report: dict[str, Any]) -> str:
    findings = report.get('findings', [])
    lines = [
        '## AI Review',
        '',
        f"Summary: {report.get('summary', 'No summary provided.')}",
        f"Overall risk: `{report.get('overall_risk', 'unknown')}`",
        f"Decision: `{report.get('decision', 'advisory-concerns')}`",
        '',
    ]
    if not findings:
        lines.append('No significant review findings.')
        return '\n'.join(lines)

    lines.append('| Severity | Category | Location | Finding | Recommendation |')
    lines.append('| --- | --- | --- | --- | --- |')
    for finding in findings:
        location = finding.get('file_path') or '<repo>'
        if finding.get('line'):
            location = f"{location}:{finding['line']}"
        lines.append(
            '| {severity} | {category} | {location} | {description} | {recommendation} |'.format(
                severity=finding.get('severity', 'unknown'),
                category=finding.get('category', 'unknown'),
                location=location,
                description=str(finding.get('description', '')).replace('|', '\\|'),
                recommendation=str(finding.get('recommendation', '')).replace('|', '\\|'),
            )
        )
    return '\n'.join(lines)


def post_pr_comment(repository: str, pr_number: int, token: str, body: str, user_agent: str) -> None:
    url = f'https://api.github.com/repos/{repository}/issues/{pr_number}/comments'
    github_post(url=url, token=token, payload={'body': body}, user_agent=user_agent)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run advisory AI review on a pull request.')
    parser.add_argument(
        '--context',
        default=str(DEFAULT_CONTEXT_PATH.relative_to(REPO_ROOT)).replace('\\', '/'),
        help='Path to docs/project/context-summary.yaml',
    )
    parser.add_argument(
        '--event-path',
        default=os.environ.get('GITHUB_EVENT_PATH'),
        help='Path to the GitHub event payload.',
    )
    parser.add_argument(
        '--repository',
        default=os.environ.get('GITHUB_REPOSITORY'),
        help='owner/repo identifier.',
    )
    parser.add_argument(
        '--provider',
        choices=['openai', 'anthropic'],
        default=os.environ.get('AI_REVIEW_PROVIDER', 'openai'),
        help='Review provider to use.',
    )
    parser.add_argument('--output', help='Optional markdown output path.')
    parser.add_argument(
        '--publish-comment',
        action='store_true',
        help='Publish the rendered review as a PR comment.',
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        context = load_project_context(args.context, repo_root=REPO_ROOT)
        if not args.event_path or not args.repository:
            raise ReviewSkip('Missing event context; skipping AI review.')

        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            raise ReviewSkip('Missing GITHUB_TOKEN; skipping AI review.')

        event = load_event(Path(args.event_path))
        pr = event.get('pull_request')
        if not pr:
            raise ReviewSkip('Event does not contain a pull_request payload; skipping AI review.')

        pr_number = int(pr['number'])
        user_agent = context['repo'].get('user_agent', 'portable-agent-ai-review')
        files = collect_pr_files(
            repository=args.repository,
            pr_number=pr_number,
            token=token,
            user_agent=user_agent,
        )
        prompt = build_review_payload(context=context, event=event, files=files)

        if args.provider == 'openai':
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                raise ReviewSkip('OPENAI_API_KEY is not configured; skipping AI review.')
            model = os.environ.get('AI_REVIEW_OPENAI_MODEL', DEFAULT_OPENAI_MODEL)
            report = call_openai(prompt=prompt, api_key=api_key, model=model)
        else:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                raise ReviewSkip('ANTHROPIC_API_KEY is not configured; skipping AI review.')
            model = os.environ.get('AI_REVIEW_ANTHROPIC_MODEL', DEFAULT_ANTHROPIC_MODEL)
            report = call_anthropic(prompt=prompt, api_key=api_key, model=model)

        markdown = render_markdown(report)
        if args.output:
            Path(args.output).write_text(markdown, encoding='utf-8')

        print(markdown)

        if args.publish_comment:
            post_pr_comment(
                repository=args.repository,
                pr_number=pr_number,
                token=token,
                body=markdown,
                user_agent=user_agent,
            )
    except ReviewSkip as exc:
        print(str(exc))
        return 0
    except (
        ContextError,
        ReviewError,
        urllib.error.HTTPError,
        urllib.error.URLError,
        OSError,
        KeyError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
