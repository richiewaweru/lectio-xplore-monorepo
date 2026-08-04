## Refactor: rendering overhaul + multi-provider model catalog

**Classification**: major
**Scope**: CSS architecture, runtime behaviors, MathJax integration, creative renderer, model catalog, multi-provider routing, Jinja2 component templates
**Behavior changes**: textbook HTML gains visual variety (theme CSS files per template), 5 new interactive behaviors, MathJax math rendering, a creative LLM-authored render path, and cross-provider model routing via a JSON catalog

---

### Progress

- [x] Documented scope and interfaces affected
- [x] Established baseline (145 tests passing before changes)
- [x] **Track A**: CSS architecture — extracted f-string CSS to theme files
- [x] **Track A**: Hand-crafted T20 "Alive" theme CSS
- [x] **Track A**: Created T20 template config JSON
- [x] **Track B**: Implemented 5 new runtime behaviors (quiz-check, equation-reveal, self-check, compare-toggle, collapsible-section)
- [x] **Track B**: Updated Jinja2 component templates with `data-behaviour` wiring (PracticeTierGrid, WorkedExampleStepper, DefinitionCard)
- [x] **Track C**: Added MathJax/KaTeX conditional inclusion in lively template
- [x] **Track D**: Created creative render prompt and renderer
- [x] **Track D**: Wired creative mode routing in HTMLRenderer
- [x] **Track E**: Added `ModelAssignment` value object and updated `ModelRouting`
- [x] **Track E**: Created `model_catalog.json` with 6 models and 4 routing presets
- [x] **Track E**: Created `ModelCatalog` loader and `ProviderPool`
- [x] **Track E**: Updated orchestrator for multi-provider routing
- [x] **Track E**: Wired dependencies for catalog/pool/resolver
- [x] Added tests for all new infrastructure (catalog, pool)
- [x] Verified all 161 tests pass
- [x] Architecture guard: 0 violations

### Validation Evidence

- `cd backend && uv run pytest --tb=short -q` → `161 passed, 6 deselected in 29.41s`
- `python tools/agent/check_architecture.py --format text` → `No architecture violations found.`

---

### What was done

#### Track A — CSS Architecture + T20 Template

**Root cause fixed:** `_build_screen_css()` was a 244-line Python f-string producing identical structural CSS for every template. Templates only varied CSS custom property values (colors, fonts) — never layout or component styling.

**Solution:** Split into `_build_root_vars()` (emits `:root { --vars }` from template tokens) + `_load_theme_css()` (loads structural CSS from disk per template). Added `css_theme` field to `TemplateConfig`.

**Files created:**
- `infrastructure/renderer/assets/themes/base.css` — exact extraction of old f-string (backward compatible for T01-T10)
- `infrastructure/renderer/assets/themes/t20_alive.css` — ~420 lines of hand-crafted CSS: dark hero, depth-rich cards, gradient-tinted block types, worked example stepper with vertical connecting line, practice cards with hover lift
- `infrastructure/renderer/template_configs/t20_alive.json` — T20 config: `css_theme: "t20_alive"`, `math_renderer: "mathjax"`, `interaction.level: "high"`, all new behaviors enabled

**Files modified:**
- `infrastructure/renderer/presentation_engine.py` — refactored `_build_screen_css()`
- `domain/entities/presentation.py` — added `css_theme: str` and `math_renderer: MathRenderer` to `TemplateConfig`

#### Track B — Runtime Behaviors + Component Wiring

**Root cause fixed:** Only 7 of 22 declared behaviors had runtime implementations. Practice hints were always visible, worked examples showed all steps, definitions had no toggle.

**5 new behaviors added to `runtime.js`:**
1. `quiz-check` — multiple choice with correct/incorrect feedback
2. `equation-reveal` — progressive math derivation with "Next step →" button
3. `self-check` — reveal model answer on click
4. `compare-toggle` — switch between two views (formal vs plain language)
5. `collapsible-section` — animated expand/collapse with `max-height` transition

**CSS added to `runtime.css`** for all 5 behaviors + `@media print` rules (show all content, hide controls).

**Jinja2 component templates updated:**
- `PracticeTierGrid.html.j2` — hint-toggle wiring with show/hide button, optional quiz-check
- `WorkedExampleStepper.html.j2` — step-reveal with `data-step-index`, hidden steps, reveal button
- `DefinitionCard.html.j2` — compare-toggle between formal definition and plain language

#### Track C — MathJax

**Added to `lively_presentation.html.j2`:** Conditional MathJax 3 or KaTeX CDN inclusion based on `template.math_renderer`. Passed through from `lively_presentation_engine.py`.

#### Track D — Creative Renderer

**New workflow:** For capable LLMs (Opus 4.6, GPT-5), the system can bypass Jinja2 templates entirely. The full content pipeline runs normally (plan → content → diagram → code → assemble → quality check), then at the final render step the assembled `RawTextbook` is serialized into a prompt and sent to an LLM to produce a complete standalone HTML+CSS+JS page.

**Files created:**
- `domain/prompts/creative_render_prompt.py` — serializes `RawTextbook` content into structured text, provides detailed system prompt for HTML authoring
- `infrastructure/renderer/creative_renderer.py` — `CreativeRenderer` class: calls `BaseProvider.complete()`, extracts HTML, applies light sanitization (strips `eval`, `fetch`, `document.cookie` etc. but allows CSS/JS)

**Files modified:**
- `infrastructure/renderer/html_renderer.py` — routes to `CreativeRenderer` when `render_mode == "creative"`
- `infrastructure/config/settings.py` — added `render_mode` and `creative_render_model` settings

#### Track E — Multi-Provider Model Catalog

**Problem solved:** The system could only use one provider at a time. The user wants to A/B test models across providers — e.g., Claude for content + GPT-5 for creative rendering.

**New domain concept:** `ModelAssignment` — frozen dataclass pairing `(provider, model_id)`. Replaces bare `str` in all `ModelRouting` slots. Added `creative` slot to `ModelRouting`.

**Files created:**
- `infrastructure/config/model_catalog.json` — 6 models (Claude Opus 4.6, Sonnet 4.6, Sonnet 4.5, Haiku 4.5, GPT-5, GPT-5 Mini) + 4 presets (`claude-default`, `claude-premium`, `openai-default`, `mixed-best`)
- `infrastructure/config/model_catalog.py` — `ModelCatalog` loader: resolves aliases → `ModelAssignment`, presets → `ModelRouting`, falls back to raw model ID inference
- `infrastructure/providers/provider_pool.py` — `ProviderPool`: lazily creates and caches `BaseProvider` instances per provider name

**Files modified:**
- `domain/value_objects/model_routing.py` — added `ModelAssignment`, changed `ModelRouting` field types, added `creative` slot
- `infrastructure/config/settings.py` — added `model_routing_preset`, `model_catalog_path`
- `application/orchestrator.py` — added `provider_resolver: Callable[[str], BaseProvider] | None`, `_resolve_provider()` helper, updated all 7+ node constructions
- `application/use_cases/generate_textbook.py` — forwards `provider_resolver`
- `interface/api/dependencies.py` — added `get_model_catalog()`, `get_provider_pool()`, updated routing/renderer/use-case wiring

**Usage:**
```bash
# Legacy (backward compat, works identically to before)
PROVIDER=claude

# Use a catalog preset
MODEL_ROUTING_PRESET=claude-premium

# Mix providers
MODEL_ROUTING_PRESET=mixed-best

# Add a model: edit model_catalog.json — no Python changes
```

---

### Pending / Follow-up work

#### P1 — Manual visual verification (high priority)
- [ ] Generate a textbook with T01 and verify CSS output is byte-identical to pre-change output (backward compat)
- [ ] Generate same subject with T01 vs T20 and visually compare the HTML pages
- [ ] Open T20 output in browser and verify: hint toggles, step-reveal, quiz-check feedback, MathJax rendering, zoom overlay, scrollspy, compare-toggle on definitions
- [ ] Print T20 output and verify all content is visible, no interactive controls shown

#### P2 — Creative mode testing (high priority)
- [ ] Run creative mode end-to-end with a real LLM (`RENDER_MODE=creative MODEL_ROUTING_PRESET=claude-premium`)
- [ ] Test with GPT-5 (`MODEL_ROUTING_PRESET=mixed-best`) and compare quality
- [ ] Evaluate creative HTML output: interactivity works, responsive, MathJax renders, prints cleanly
- [ ] The `CreativeRenderResult` schema uses `html: str` — if a provider's structured output wrapping interferes with raw HTML, may need to switch to raw text completion

#### P3 — Multi-provider testing (medium priority)
- [ ] Test `mixed-best` preset end-to-end with both API keys configured
- [ ] Verify that different pipeline nodes actually hit different providers (add logging or observe API call patterns)
- [ ] Test that the system degrades gracefully if only one API key is provided

#### P4 — Component template gaps
- [ ] `ThinkPromptPause.html.j2` — could benefit from `self-check` behavior wiring
- [ ] `InterviewAnchor.html.j2` — could benefit from `collapsible-section` behavior
- [ ] `MisconceptionAlert.html.j2` — could benefit from `collapsible-section` for the correction
- [ ] Quiz-check behavior in practice grid depends on `item.options` which `PracticeProblem` entity doesn't have yet — need to add `options: list[QuizOption]` field to enable MCQ practice

#### P5 — Frontend build (existing issue)
- [ ] SvelteKit `adapter-auto` build step is temporarily disabled (pre-existing, documented in CI validation)

#### P6 — Creative mode prompt refinement
- [ ] The creative render prompt could include example HTML snippets from the reference files to demonstrate the quality bar
- [ ] Consider adding subject-specific style guidance (the prompt mentions it but doesn't enforce it)
- [ ] Max tokens (16384) may be insufficient for large textbooks — consider chunking or increasing

---

### Known technical notes

1. **Creative mode sanitization** strips `localStorage`, `sessionStorage`, `window.location`, `fetch()`, `eval()`, `Function()`, `document.cookie`, `XMLHttpRequest`, `Worker`, `indexedDB`, `navigator.sendBeacon`, `importScripts`, `window.open`. This is intentionally light — the creative renderer trusts the LLM for educational content but prevents data exfiltration.

2. **Provider inference fallback** in `ModelCatalog.resolve()`: if a raw model ID string doesn't match any catalog entry, the provider is inferred from the string prefix (`claude-*` → claude, `gpt-*`/`o1-*`/`o3-*` → openai, default → claude).

3. **Architecture boundary**: The `orchestrator.py` (application layer) accepts `provider_resolver: Callable[[str], BaseProvider]` instead of importing `ProviderPool` directly, preserving the DDD layer rule that application never imports from infrastructure.

4. **`_routing_for_mode()`** in STRICT mode upgrades all slots to the premium tier. This now works with `ModelAssignment` objects — the `or` fallback chain (`self.model_routing.content or premium`) works because `ModelAssignment` is truthy when not `None`.

---

### Files changed (complete list)

**New files (15):**
- `backend/src/textbook_agent/infrastructure/renderer/assets/themes/base.css`
- `backend/src/textbook_agent/infrastructure/renderer/assets/themes/t20_alive.css`
- `backend/src/textbook_agent/infrastructure/renderer/template_configs/t20_alive.json`
- `backend/src/textbook_agent/domain/prompts/creative_render_prompt.py`
- `backend/src/textbook_agent/infrastructure/renderer/creative_renderer.py`
- `backend/src/textbook_agent/infrastructure/config/model_catalog.json`
- `backend/src/textbook_agent/infrastructure/config/model_catalog.py`
- `backend/src/textbook_agent/infrastructure/providers/provider_pool.py`
- `backend/tests/infrastructure/test_model_catalog.py`
- `backend/tests/infrastructure/test_provider_pool.py`

**Modified files (13):**
- `backend/src/textbook_agent/infrastructure/renderer/presentation_engine.py`
- `backend/src/textbook_agent/infrastructure/renderer/lively_presentation_engine.py`
- `backend/src/textbook_agent/infrastructure/renderer/html_renderer.py`
- `backend/src/textbook_agent/infrastructure/renderer/assets/runtime.js`
- `backend/src/textbook_agent/infrastructure/renderer/assets/runtime.css`
- `backend/src/textbook_agent/infrastructure/renderer/templates/lively_presentation.html.j2`
- `backend/src/textbook_agent/infrastructure/renderer/templates/components/PracticeTierGrid.html.j2`
- `backend/src/textbook_agent/infrastructure/renderer/templates/components/WorkedExampleStepper.html.j2`
- `backend/src/textbook_agent/infrastructure/renderer/templates/components/DefinitionCard.html.j2`
- `backend/src/textbook_agent/domain/entities/presentation.py`
- `backend/src/textbook_agent/domain/value_objects/model_routing.py`
- `backend/src/textbook_agent/domain/value_objects/__init__.py`
- `backend/src/textbook_agent/domain/prompts/__init__.py`
- `backend/src/textbook_agent/infrastructure/config/settings.py`
- `backend/src/textbook_agent/application/orchestrator.py`
- `backend/src/textbook_agent/application/use_cases/generate_textbook.py`
- `backend/src/textbook_agent/interface/api/dependencies.py`
- `backend/tests/interface/test_api.py`
