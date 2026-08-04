#!/usr/bin/env python3
"""
Basic smoke test for a deployed Textbook Agent backend.

Usage:
    python scripts/smoke_test.py https://your-app.up.railway.app
"""

from __future__ import annotations

import sys

import httpx


def run(base_url: str) -> bool:
    base = base_url.rstrip("/")
    client = httpx.Client(base_url=base, timeout=15)
    failures: list[str] = []

    def check(label: str, response: httpx.Response, expected_status: int = 200) -> bool:
        if response.status_code != expected_status:
            failures.append(
                f"FAIL  {label}: expected {expected_status}, got {response.status_code}"
            )
            print(failures[-1])
            return False
        print(f"OK    {label}")
        return True

    try:
        check("GET /health", client.get("/health"))

        readiness = client.get("/health/ready")
        if check("GET /health/ready", readiness):
            data = readiness.json()
            if data.get("status") != "ok":
                failures.append(
                    f"FAIL  /health/ready status is '{data.get('status')}', not 'ok'"
                )
                print(failures[-1])
            else:
                dependencies = [
                    f"{dep['name']}={dep['status']}" for dep in data.get("dependencies", [])
                ]
                print(f"      dependencies: {dependencies}")
                generations = data.get("generations")
                if generations:
                    print(
                        "      generations: "
                        f"running={generations['running']} pending={generations['pending']}"
                    )

        auth_route = client.post("/api/v1/auth/google", json={})
        if auth_route.status_code == 404:
            failures.append("FAIL  POST /api/v1/auth/google: route not found")
            print(failures[-1])
        else:
            print(
                "OK    POST /api/v1/auth/google "
                f"(status {auth_route.status_code}, route exists)"
            )

        protected = client.get("/api/v1/generations")
        check("GET /api/v1/generations (no auth -> 401)", protected, expected_status=401)
    finally:
        client.close()

    print()
    if failures:
        print(f"Smoke test FAILED - {len(failures)} failure(s)")
        return False

    print("Smoke test PASSED")
    return True


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    raise SystemExit(0 if run(url) else 1)
