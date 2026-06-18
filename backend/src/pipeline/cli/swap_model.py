"""
CLI tool to update one slot-based model override in the backend `.env` file.

Usage:
  python -m pipeline.cli.swap_model --slot fast --provider openai_compatible --model llama3-8b-8192 --base-url https://api.groq.com/openai/v1 --api-key-env GROQ_API_KEY
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    """Replace or append the provided key/value pairs in the target env file."""

    if not env_path.exists():
        lines = []
    else:
        with open(env_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

    for key, value in updates.items():
        pattern = re.compile(rf"^{key}=.*")
        found = False
        for index, line in enumerate(lines):
            if pattern.match(line):
                lines[index] = f"{key}={value}\n"
                found = True
                break
        if not found:
            lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as file:
        file.writelines(lines)

    print(f"Updated {env_path.name}")
    for key, value in updates.items():
        print(f"   {key}={value}")


def main() -> None:
    """Parse slot-based override args and persist them to the backend env file."""

    parser = argparse.ArgumentParser(
        description="Swap the model family for a pipeline slot.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--slot",
        choices=["fast", "standard", "creative"],
        required=True,
        help="Pipeline slot to update.",
    )
    parser.add_argument(
        "--provider",
        required=True,
        help="Transport family (e.g., anthropic, google, openai_compatible).",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Model name to assign to the slot.",
    )
    parser.add_argument(
        "--base-url",
        help="Base URL for openai_compatible providers.",
    )
    parser.add_argument(
        "--api-key-env",
        help="Optional API key env var name to use for this slot.",
    )

    if "--route" in sys.argv[1:]:
        parser.error("--route has been removed; use --slot")

    args = parser.parse_args()

    if args.provider == "openai_compatible" and not args.base_url:
        parser.error("--base-url is required when using the 'openai_compatible' provider")

    prefix = f"PIPELINE_{args.slot.upper()}"
    updates = {
        f"{prefix}_PROVIDER": args.provider,
        f"{prefix}_MODEL_NAME": args.model,
    }
    if args.base_url:
        updates[f"{prefix}_BASE_URL"] = args.base_url
    if args.api_key_env:
        updates[f"{prefix}_API_KEY_ENV"] = args.api_key_env

    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    update_env_file(env_path.resolve(), updates)


if __name__ == "__main__":
    main()
