from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the V3 image diagnostic harness against grok, the V3 GCS store, "
            "and the full V3 visual executor."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help=(
            "Optional .env file to preload before backend settings import. "
            "Useful when you want to point the harness at the repo-root Docker env."
        ),
    )
    return parser.parse_args()


async def _main() -> int:
    args = _parse_args()
    if args.env_file is not None:
        env_path = args.env_file
        if not env_path.is_absolute():
            env_path = (PROJECT_ROOT / env_path).resolve()
        load_dotenv(env_path, override=True)
        import os

        os.environ["V3_IMAGE_DIAGNOSTIC_ENV_FILE"] = str(env_path)

    from core.config import settings
    from core.logging import configure_logging
    from media.diagnostics.v3_image_pipeline_diagnostic import (
        format_report,
        run_diagnostic,
    )

    configure_logging(json_logs=False, level=20)
    report = await run_diagnostic()
    print(format_report(report), end="")
    return 0 if all(result.ok for result in report.results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
