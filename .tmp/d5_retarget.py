from pathlib import Path
import re
import shutil

ROOT = Path(r"C:\Projects\lectio\apps\textbook-agent")
SRC = ROOT / "backend" / "src"
TESTS = ROOT / "backend" / "tests"
FE = ROOT / "frontend" / "src"

# 1) Move real modules into canonical homes
moves = [
    (SRC / "generation" / "canonical.py", SRC / "learn" / "generation" / "canonical.py"),
    (SRC / "generation" / "signal_map.py", SRC / "print" / "http" / "v3_studio" / "generation_signal_map.py"),
    (SRC / "planning" / "projections.py", SRC / "curriculum" / "projections.py"),
    (SRC / "planning" / "llm_contract_errors.py", SRC / "curriculum" / "llm_contract_errors.py"),
    (SRC / "planning" / "planner_diagnostics.py", SRC / "curriculum" / "planner_diagnostics.py"),
    (SRC / "planning" / "structural_validation.py", SRC / "curriculum" / "structural_validation.py"),
    (SRC / "planning" / "model_tiers.py", SRC / "print" / "generation" / "model_tiers.py"),
    (SRC / "planning" / "catalogue_projections.py", SRC / "print" / "generation" / "catalogue_projections.py"),
    (SRC / "planning" / "models.py", SRC / "curriculum" / "path_models.py"),
]
for src, dst in moves:
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"moved {src.name} -> {dst}")
    elif src.exists() and dst.exists():
        # prefer dest; drop source if identical-ish
        print(f"dest exists, remove source {src}")
        src.unlink()

# 2) Bulk import rewrite
REPLACEMENTS = [
    (r"\bgeneration\.v3_studio\b", "print.http.v3_studio"),
    (r"\bgeneration\.pdf_export\b", "print.rendering.pdf"),
    (r"\bgeneration\.path_preparation\b", "application.unit_lesson"),
    (r"\bgeneration\.contracts\b", "learn.generation.contracts"),
    (r"\bgeneration\.pipeline_dispatch\b", "learn.generation.pipeline_dispatch"),
    (r"\bgeneration\.units_routes\b", "learn.generation.units_routes"),
    (r"\bgeneration\.units_dispatch\b", "learn.generation.units_dispatch"),
    (r"\bgeneration\.canonical\b", "learn.generation.canonical"),
    (r"\bgeneration\.signal_map\b", "print.http.v3_studio.signal_map"),
    (r"\bplanning\.whole_lesson\b", "print.generation.whole_lesson"),
    (r"\bplanning\.agents\b", "curriculum.agents"),
    (r"\bplanning\.approved_items\b", "curriculum.approved_items"),
    (r"\bplanning\.bridge\b", "application.unit_lesson"),
    (r"\bplanning\.prompts\b", "curriculum.prompts"),
    (r"\bplanning\.validation\b", "curriculum.validation"),
    (r"\bplanning\.projections\b", "curriculum.projections"),
    (r"\bplanning\.llm_contract_errors\b", "curriculum.llm_contract_errors"),
    (r"\bplanning\.planner_diagnostics\b", "curriculum.planner_diagnostics"),
    (r"\bplanning\.structural_validation\b", "curriculum.structural_validation"),
    (r"\bplanning\.model_tiers\b", "print.generation.model_tiers"),
    (r"\bplanning\.catalogue_projections\b", "print.generation.catalogue_projections"),
    (r"\bplanning\.models\b", "curriculum.path_models"),
    (r"\bfrom telemetry\.", "from infra.telemetry."),
    (r"\bimport telemetry\b", "import infra.telemetry"),
    (r"\bfrom builder\.", "from learn.authoring.builder."),
    (r"\bfrom learning\.", "from learn."),
    (r"\bimport learning\b", "import learn"),
]

scan_roots = [SRC, TESTS, FE]
exts = {".py", ".ts", ".svelte", ".md"}
changed = 0
for root in scan_roots:
    for path in root.rglob("*"):
        if path.suffix not in exts or "__pycache__" in path.parts:
            continue
        # skip files we're about to delete inside planning/generation shims
        text = path.read_text(encoding="utf-8")
        new = text
        for pat, repl in REPLACEMENTS:
            new = re.sub(pat, repl, new)
        # studio FE packs redirects -> units
        if path.suffix in {".ts", ".svelte"}:
            new = new.replace("goto(`/packs/${encodeURIComponent(resolved.pack_id)}`)", "goto('/units')")
            new = new.replace("goto(`/packs/${encodeURIComponent(next.pack_id)}`)", "goto('/units')")
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
            print("rewrote", path.relative_to(ROOT))
print("files_changed", changed)
