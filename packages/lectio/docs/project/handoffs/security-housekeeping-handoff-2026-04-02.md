# Handoff: Security Patch & Housekeeping — v0.1.1

**Date:** 2026-04-02
**Branch:** claude/eloquent-edison
**Version:** 0.1.1 (patch)

---

## What Was Done

### 1. Docs Organisation
Moved two large spec files from root into `docs/project/` where all internal project docs live:
- `lectio-harmonisation-spec.md` → `docs/project/lectio-harmonisation-spec.md`
- `LECTIO_COMPLETE_BUILD.md` → `docs/project/LECTIO_COMPLETE_BUILD.md`

Deleted `AGENTS.md` at root — it was a byte-for-byte duplicate of `CLAUDE.md` and served no purpose.

Created `.env.example` at root (`.gitignore` already whitelisted it but the file was missing). Placeholder only — no server-side variables required yet.

---

### 2. Security — HIGH: XSS in ExplanationBlock

**File:** `src/lib/components/lectio/ExplanationBlock.svelte`

**Problem:** `highlightEmphasis(content.body, content.emphasis)` rendered `content.body` as raw HTML via `{@html}` without escaping it first. AI-generated body text containing `<script>` tags or `onerror=` event handlers would have executed in the browser.

**Fix:** Added `escapeHtml()` helper that HTML-encodes `&`, `<`, `>`, `"`, `'` before any regex replacements run. The `<mark>` injection that follows is safe because it only wraps already-escaped text.

---

### 3. Security — MEDIUM: Raw SVG @html in 5 Components

**Files:**
- `src/lib/components/lectio/DiagramBlock.svelte` (2 occurrences)
- `src/lib/components/lectio/DiagramCompare.svelte` (4 occurrences)
- `src/lib/components/lectio/DiagramSeries.svelte` (2 occurrences)
- `src/lib/components/lectio/HookHero.svelte` (1 occurrence)
- `src/lib/components/lectio/SimulationBlock.svelte` (2 occurrences)

**Problem:** 11 `{@html svg_content}` calls rendered AI-generated SVG without sanitization. Malicious SVG can embed `<script>` tags or inline event handlers (`onload`, `onclick`, etc.).

**Fix:**
- Installed `dompurify` + `@types/dompurify`
- Created `src/lib/utils/sanitize.ts` with a `sanitizeSvg(svg)` util using DOMPurify's SVG + svgFilters profile
- Wrapped every SVG `{@html}` call: `{@html sanitizeSvg(content.svg_content)}`
- `sanitizeSvg` accepts `string | undefined` and returns `''` for falsy input — no extra null-guards needed in templates

---

## What Was NOT Changed

- `MathFormula.svelte` — uses KaTeX output, already safe
- `guided-discovery/preview.ts` — `svg.innerHTML` is inside a sandboxed iframe (`allow-scripts` without `allow-same-origin`), constructs SVG from math calculations only, no user input path
- `.npmrc` — hardcoded GitHub Packages registry URL is intentional and correct
- No CORS changes needed — library has no server routes

---

## Verification

- `npm run check` — 0 errors, 0 warnings
- `npm run build` — succeeded (4546 modules, built in ~2 min)

---

## Next Steps

- As integrations are added (e.g. API routes, Gemini), add env vars to `.env.example`
- If SSR ever becomes a requirement, replace `dompurify` with `isomorphic-dompurify`
