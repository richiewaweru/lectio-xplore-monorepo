from pathlib import Path

NEEDLES = ("KEY", "TOKEN", "SECRET", "PROVIDER", "MODEL", "DEEPSEEK", "OPENAI", "ANTHROPIC", "GOOGLE", "GEMINI")
roots = [
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\.env"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\.env"),
    Path(r"C:\Projects\lectio\.env"),
]
found = False
for p in roots:
    if not p.exists():
        print(f"missing {p}")
        continue
    found = True
    print(f"env_file {p}")
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if any(n in k.upper() for n in NEEDLES):
            status = "SET" if v else "EMPTY"
            print(f"{k}: {status} len={len(v)}")
if not found:
    print("NO_ENV_FILES")
