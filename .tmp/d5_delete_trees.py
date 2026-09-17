from pathlib import Path
import shutil

SRC = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src")
FE = Path(r"C:\Projects\lectio\apps\textbook-agent\frontend\src\routes")

DELETE_DIRS = [
    SRC / "builder",
    SRC / "learning",
    SRC / "telemetry",
    SRC / "generation",
    SRC / "planning",
]
DELETE_FE = [
    FE / "packs",
    FE / "units" / "legacy",
    FE / "builder" / "new",
]

# Dead generation-only tests / shadow gate
DELETE_FILES = [
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests\routes\test_blocks_generate.py"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests\services\test_generation_failure.py"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests\core\test_logging.py"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests\v3_blueprint\test_skeletons.py"),  # uses preview_skeletons HTTP helper
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\scripts\run_v2_shadow_gate.py"),
    SRC / "print" / "http" / "v3_studio" / "generation_signal_map.py",  # duplicate; signal_map.py is canonical
]

for d in DELETE_DIRS:
    if d.exists():
        shutil.rmtree(d)
        print("deleted dir", d)

for d in DELETE_FE:
    if d.exists():
        shutil.rmtree(d)
        print("deleted fe", d)

for f in DELETE_FILES:
    if f.exists():
        f.unlink()
        print("deleted file", f)

print("done")
