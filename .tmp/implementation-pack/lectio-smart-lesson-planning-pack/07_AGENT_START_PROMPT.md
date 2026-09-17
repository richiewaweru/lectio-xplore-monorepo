# Startup Prompt for the Implementation Agent

You are implementing the Smart Lesson Planning + Coherence pass in the Lectio repository.

Repository: `richiewaweru/lectio-xplore-monorepo`
Expected baseline: `main@af7a3d46e684d9752c6e18034f9b86b322348936` or a later main that contains the same closed Print/Learn architecture. If main moved, inspect the diff first and adapt; do not blindly apply old paths.

Read this pack in order beginning with `00_READ_ME_FIRST.md`.

Your job is to implement the architecture, prompt changes, tests, and live proofs described here. The purpose is to improve the quality and coherence of the **shared lesson** before any visual primitive redesign.

Non-negotiable boundaries:

- Print and Learn remain independent realizations of one approved shared Teaching Plan.
- No Print → Learn or Learn → Print conversion.
- Do not reintroduce the old generic component architecture.
- Preserve the six shared ordinary document primitives.
- Preserve closed Learn interactions and Print-local treatments.
- Skeletons remain useful pedagogical defaults, but their exact order must no longer be an unconditional prison.
- Formative response tasks may be shared without approved assessment items; formal assessment items retain strict approved-source ownership.
- A path may never invent a response task that does not exist in shared task state.
- Concrete lesson facts/examples/data must be bound through the shared sourcebook when consistency matters.
- Whole-lesson review must return targeted repair targets; never regenerate a lesson wholesale as the normal repair strategy.
- All new LLM stages must use the repository's authoring/prompt loader, budgets, checkpoints, observability and revision identity patterns.

Work phase-by-phase. After each phase, run its gate and save exact evidence. Do not weaken a failing test just to continue.

At the end:

1. run regression suites;
2. run planner-only cross-subject fixtures;
3. generate fresh Math, History and Biology lessons;
4. generate both Print and Learn from the same approved Teaching Plan revision;
5. save flow, Teaching Plan, sourcebook, shared tasks, outputs, coherence reports and repair events;
6. provide a concise implementation report listing changed files, tests, live outputs, remaining limitations, and anything that should be inspected manually.

Do not begin UI styling or primitive visual redesign in this pass.
