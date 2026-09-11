# Phase F — Figures + section structure

Status: PASS

## CHANGE
Absolute `local_image_store_root()` + FastAPI mount; Vite `/images` proxy; LearnDocument `sections` metadata; builder/runtime section tabs.

## LIVE PROOF
Browser fetch:
- via Vite `http://localhost:5173/images/learn-out-f714f22eda7a/...png` → 200 image/png
- via backend `:8000/images/...` → 200

LearnDocument sections assembled in `native_production._realized_sections`.

## STATUS
PASS
