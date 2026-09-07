#!/usr/bin/env python3
"""Validate this proposal pack's structure, examples and checksums, not the application."""
import csv, hashlib, json, pathlib, re
root = pathlib.Path(__file__).resolve().parents[1]
files = [p for p in root.rglob("*") if p.is_file() and "__pycache__" not in str(p)]
for p in files:
    if p.suffix == ".json":
        json.loads(p.read_text())
plan = json.loads((root/"tracking/phase-plan.json").read_text())
phases = plan["phases"]
ids = {p["id"] for p in phases}
assert len(ids) == len(phases) == 10
seen = set()
expected = set()
for phase in phases:
    assert set(phase["depends_on"]) <= seen
    seen.add(phase["id"])
    doc = root/phase["document"]
    assert doc.is_file(), doc
    for gate in phase["gates"]:
        assert gate in doc.read_text(), gate
        expected.add(gate)
rows = list(csv.DictReader((root/"tracking/GATE_RESULTS.csv").open()))
assert {r["gate"] for r in rows} == expected
assert len(rows) == len(expected) == 59
assert all(r["status"] == "NOT_RUN" for r in rows)
state = json.loads((root/"tracking/STATE.json").read_text())
assert set(state["phases"]) == ids
assert all(p["status"] == "NOT_STARTED" for p in state["phases"].values())
shared = json.loads((root/"examples/cycle-shared-plan.json").read_text())
block_ids = [b["id"] for s in shared["slots"] for b in s["blocks"]]
assert len(block_ids) == len(set(block_ids))
native = json.loads((root/"examples/cycle-native-decisions.json").read_text())
for path in ("print", "learn"):
    assert [x["block_id"] for x in native[path]] == block_ids
assert "capability" not in json.dumps(shared)
# This pack uses only the following JSON Schema keywords in its illustrative schema.
# Validate that closed subset explicitly, with no third-party dependency.
# This is not the production application's schema validator.
def validate_example(value, spec, path="$"):
    supported = {"$schema", "title", "type", "additionalProperties", "required", "properties", "enum", "minLength", "items", "uniqueItems"}
    assert set(spec) <= supported, (path, "unsupported schema keyword")
    types = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list), "string": lambda v: isinstance(v, str), "null": lambda v: v is None}
    declared = spec.get("type")
    if declared:
        allowed = declared if isinstance(declared, list) else [declared]
        assert all(t in types for t in allowed), (path, "unsupported type")
        assert any(types[t](value) for t in allowed), (path, "type")
    if "enum" in spec:
        assert value in spec["enum"], (path, "enum")
    if "minLength" in spec:
        assert len(value) >= spec["minLength"], (path, "minLength")
    if isinstance(value, dict):
        assert set(spec.get("required", [])) <= set(value), (path, "required")
        props = spec.get("properties", {})
        if spec.get("additionalProperties") is False:
            assert set(value) <= set(props), (path, "additionalProperties")
        for key, item in value.items():
            if key in props:
                validate_example(item, props[key], path+"."+key)
    if isinstance(value, list):
        if spec.get("uniqueItems"):
            assert len({json.dumps(v, sort_keys=True) for v in value}) == len(value), (path, "uniqueItems")
        for i, item in enumerate(value):
            validate_example(item, spec["items"], path+"["+str(i)+"]")
validate_example(json.loads((root/"examples/sequence-capability.json").read_text()), json.loads((root/"examples/capability.schema.json").read_text()))
manifest = root/"MANIFEST.json"
if manifest.exists():
    entries = json.loads(manifest.read_text())["files"]
    for e in entries:
        p = root/e["path"]
        assert p.is_file(), p
        assert hashlib.sha256(p.read_bytes()).hexdigest() == e["sha256"], p
print(f"PASS: {len(phases)} phases, {len(rows)} gates; JSON, examples, dependencies and manifest verified.")
print("Application implementation and live gates remain NOT_RUN.")
