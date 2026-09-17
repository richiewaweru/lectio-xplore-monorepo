from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(r"C:\Projects\lectio")
SRC = ROOT / "apps/textbook-agent/backend/src"
FE = ROOT / "apps/textbook-agent/frontend/src"
TESTS = ROOT / "apps/textbook-agent/backend/tests"


def list_routes() -> None:
    print("ROUTES:")
    for p in sorted((FE / "routes").rglob("+page.svelte")):
        print(" ", str(p.relative_to(FE / "routes")).replace("\\", "/"))


def list_api() -> None:
    api_pat = re.compile(r"""["'`](/api/v1/[A-Za-z0-9_\-/{}$:]+)""")
    hits: dict[str, list[str]] = {}
    for f in list(FE.rglob("*.ts")) + list(FE.rglob("*.svelte")):
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in api_pat.finditer(text):
            hits.setdefault(m.group(1), []).append(
                str(f.relative_to(FE)).replace("\\", "/")
            )
    print("\nAPI ENDPOINTS:")
    for ep in sorted(hits):
        print(f"  {ep}  <- {len(hits[ep])} files")
        for c in hits[ep][:2]:
            print(f"      {c}")


def inbound_imports() -> None:
    pkgs = [
        "planning",
        "generation",
        "learning",
        "builder",
        "core",
        "telemetry",
        "resource_specs",
        "contracts",
        "media",
        "v3_blueprint",
        "v3_execution",
        "v3_review",
        "application",
    ]
    files = [f for f in SRC.rglob("*.py") if "__pycache__" not in str(f)]
    for pkg in pkgs:
        pat = re.compile(rf"(?:from|import)\s+{re.escape(pkg)}(?:\.|\s|$)")
        inbound = []
        for f in files:
            rel = str(f.relative_to(SRC)).replace("\\", "/")
            if rel == pkg or rel.startswith(pkg + "/"):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            if pat.search(text):
                inbound.append(rel)
        print(f"\n=== inbound to {pkg}: {len(inbound)} ===")
        for i in sorted(inbound)[:30]:
            print(" ", i)
        if len(inbound) > 30:
            print(f"  ... +{len(inbound) - 30}")


def list_legacy_tests() -> None:
    keywords = ("legacy", "v3_studio", "blocks_generate", "packs", "skeleton")
    print("\nLEGACY-ISH TESTS:")
    for f in sorted(TESTS.rglob("*.py")):
        name = str(f.relative_to(TESTS)).replace("\\", "/")
        if any(k in name.lower() for k in keywords):
            print(" ", name)


if __name__ == "__main__":
    list_routes()
    list_api()
    inbound_imports()
    list_legacy_tests()
