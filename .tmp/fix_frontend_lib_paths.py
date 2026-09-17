from pathlib import Path

root = Path(r"apps/textbook-agent/frontend")
exts = {".ts", ".svelte", ".js", ".tsx"}
flags = root / "src/lib/shared/settings/flags.ts"
flags2 = root / "src/lib/settings/flags.ts"
print("flags shared", flags.exists(), "old", flags2.exists())

replacements = [
    ("$lib/builder/", "$lib/learn/authoring/builder/"),
    (
        "$lib/components/learn/shared/authoring/workspace/",
        "$lib/components/workspace/",
    ),
]
if flags.exists():
    replacements.append(("$lib/settings/flags", "$lib/shared/settings/flags"))

changed = []
for p in root.rglob("*"):
    if p.suffix not in exts or "node_modules" in p.parts or ".svelte-kit" in p.parts:
        continue
    text = p.read_text(encoding="utf-8")
    new = text
    for a, b in replacements:
        new = new.replace(a, b)
    if new != text:
        p.write_text(new, encoding="utf-8", newline="\n")
        changed.append(p.as_posix())
print("changed", len(changed))

patterns = [
    "$lib/builder/",
    "$lib/learn/shared",
    "$lib/components/print/studio",
    "/print/studio",
    "/learn/shared/authoring",
    "/api/v1/learn/shared",
    "/api/v1/shared/auth",
    "$lib/components/learn/shared",
]
for pat in patterns:
    f = n = 0
    samples = []
    for p in root.rglob("*"):
        if p.suffix not in exts or "node_modules" in p.parts:
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        c = t.count(pat)
        if c:
            f += 1
            n += c
            if len(samples) < 3:
                samples.append(p.as_posix())
    print(f"residual {pat!r}: files={f} hits={n} samples={samples}")
