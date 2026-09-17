#!/usr/bin/env python3
from pathlib import Path
import re

root = Path(r"c:\Projects\lectio\packages\lectio-learn\src\lib\lectio\components")
for d in sorted(root.iterdir()):
    if not d.is_dir():
        continue
    mt = (d / "metadata.ts").read_text(encoding="utf-8") if (d / "metadata.ts").exists() else ""
    mod = (d / "module.ts").read_text(encoding="utf-8") if (d / "module.ts").exists() else ""
    status = re.search(r"status:\s*'([^']+)'", mt)
    phase = re.search(r"phase:\s*(\d+)", mt)
    eval_ = re.search(r"responseEvaluation:\s*'([^']+)'", mod)
    is_media = "isMedia: true" in mt or "isMedia: true" in mod
    print(f"{d.name}\tstatus={status.group(1) if status else '?'}\tphase={phase.group(1) if phase else '?'}\teval={eval_.group(1) if eval_ else 'none'}\tisMedia={is_media}")
