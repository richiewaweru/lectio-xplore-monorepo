# C3 PHASE PLAN — Dead-Code Removal

## Delete now (DEAD_CONFIRMED from C0 + re-verified)
- `generation/canonical_routes.py` — unmounted, zero importers
- `generation/retirement.py` — unmounted, zero importers

## Do not delete yet (still mounted or shimmed with callers)
- `print/http/v3_studio` (live Unit Print + studio UX)
- skeletons / block-generate / legacy-units / packs routers
- shim packages with live imports

## Verify
re-check zero importers; create_app; domain-guards; focused pytest.
