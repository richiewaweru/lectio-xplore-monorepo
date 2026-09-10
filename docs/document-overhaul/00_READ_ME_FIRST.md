# Lectio Document + Interaction Overhaul

Repository: `richiewaweru/lectio-xplore-monorepo`  
Baseline branch: `main`  
Baseline commit inspected: `1dabd746af65ac9d9272fcb7c49f000632407754`  
Program type: **major clean-cut architecture overhaul**

## Goal

Replace the ordinary Learn component architecture with a small document vocabulary plus a deliberately small set of true interactions.

```text
Instruction Model
        ↓
Teaching Plan
+ learner tasks
        ↓
    Path Choice
      /     \
   PRINT    LEARN
     │        │
 document   document
 + print    + supported
 treatments interactions
     │        │
    PDF      WEB
```

## Locked decisions

- Learner tasks are committed in the shared Teaching Plan before Print/Learn is known.
- Minimal learner-task meaning: `action`, `target`, `purpose`, `expected_evidence`, `difficulty`.
- Ordinary document vocabulary: `Paragraph`, `Heading`, `List`, `Figure`, `Table`, `Callout`.
- No generic `Media` for this overhaul.
- No video, audio, simulations, 3D, or other unsupported media.
- Strict schemas are reserved for actual learner interactions.
- Print and Learn are independent realizations of the same approved Teaching Plan.
- There is no Print → Learn or Learn → Print conversion.
- If a teacher later wants the other path, generate it again from the Teaching Plan.
- Ruled lines, response space, pagination, page sizing, and PDF rules are Print-only.
- Existing ordinary component generation is not preserved for compatibility.
- Old generated lessons do not need migration support.
- Keep the dashboard, auth, Unit path, Teaching Plan foundation, persistence/runtime infrastructure, and other machinery only where it serves the new architecture.
- By the end, the old ordinary component route must be physically removed from the production path.

## Important discovery from the current repo

The repo has already done some of the difficult separation work:

- `backend/src/app.py` is the FastAPI composition root; there is no active `main.py` entrypoint.
- `curriculum/teaching_plan/` already owns path-agnostic teaching meaning and already has `learner_action`.
- `application/unit_lesson/realizations.py` already models independent Print/Learn realizations pinned to a Teaching Plan revision.
- Print already has a form-selection/page pipeline that can donate useful document-form logic.
- Learn currently still has the component-heavy selection/execution architecture that this program replaces.

## Execution rule

Do not implement from memory. For every phase:
1. Re-read the phase file.
2. Open every listed active file before changing it.
3. Search for downstream references to any symbol/file being changed or deleted.
4. Establish the phase baseline.
5. Make the smallest coherent cut.
6. Run the phase gate.
7. Record exact validation evidence.
8. Do not carry compatibility code merely to protect old lesson artifacts.

Start with `repo-map/01_ACTIVE_ENTRYPOINTS.md`, then `repo-map/02_CURRENT_TO_TARGET_MAP.md`, then execute phases A → O.
