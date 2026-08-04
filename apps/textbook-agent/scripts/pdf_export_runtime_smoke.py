#!/usr/bin/env python3
from __future__ import annotations

import sys

import httpx


def run(base_url: str) -> bool:
    base = base_url.rstrip("/")
    with httpx.Client(base_url=base, timeout=15) as client:
        response = client.get("/health/deep")
    if response.status_code != 200:
        print(f"FAIL  GET /health/deep returned {response.status_code}")
        return False

    payload = response.json()
    dependencies = {dep["name"]: dep for dep in payload.get("dependencies", [])}
    required = ("playwright", "pdf_temp_dir")
    failures = []
    for name in required:
        status = dependencies.get(name, {}).get("status")
        if status != "ok":
            failures.append(f"{name}={status!r}")

    if failures:
        print("FAIL  PDF export runtime unhealthy: " + ", ".join(failures))
        return False

    exports = payload.get("pdf_exports", {})
    print("OK    PDF export runtime healthy")
    print(
        "      exports: "
        f"total={exports.get('total_exports', 0)} "
        f"success={exports.get('successful_exports', 0)} "
        f"failed={exports.get('failed_exports', 0)}"
    )
    return True


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    raise SystemExit(0 if run(url) else 1)
