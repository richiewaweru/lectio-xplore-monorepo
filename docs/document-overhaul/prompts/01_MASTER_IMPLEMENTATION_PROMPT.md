# Master Implementation Prompt

You are implementing a major architecture overhaul in `richiewaweru/lectio-xplore-monorepo`.

Baseline inspected by the planning pass: `1dabd746af65ac9d9272fcb7c49f000632407754` on `main`.

## Mandatory first reads

1. `apps/textbook-agent/AGENTS.md`
2. `apps/textbook-agent/agents/ENTRY.md`
3. `apps/textbook-agent/agents/project.md`
4. `apps/textbook-agent/agents/workflows/refactor.md`
5. `docs/architecture/CURRENT_SYSTEM.md`
6. this implementation pack, starting with `00_READ_ME_FIRST.md`

Create a visible tracking checklist before modifying code.

## Product target

```text
Instruction Model
        ↓
Teaching Plan
+ path-agnostic learner tasks
        ↓
explicit Path Choice
      /          \
   PRINT         LEARN
     │             │
document forms   document forms
+ print tasks    + retained interactions
     │             │
PrintDocument   LearnDocument
     │             │
page/PDF        editable web/runtime
```

Ordinary document vocabulary is exactly:
`Paragraph`, `Heading`, `List`, `Figure`, `Table`, `Callout`.

Do not add generic Media, video, simulation, or unsupported rich-media abstractions in this program.

Learner-task meaning belongs in the Teaching Plan. Minimum semantic fields:
`action`, `target`, `purpose`, `expected_evidence`, `difficulty`.
Do not put native UI/form/component IDs there.

## Critical constraints

- Print and Learn are independent realizations of the approved Teaching Plan.
- Do not build Print ↔ Learn conversion.
- Strict schemas belong to true interactions only.
- Normal content must not use ExplanationBlock/DefinitionBlock/etc.
- Do not preserve old lesson compatibility.
- Do not maintain a legacy fallback after cutover.
- Keep existing infrastructure only when it serves the new architecture.
- Keep dashboard/auth/Unit-path foundations unless directly coupled to retired code.
- Preserve strong retries, traceability and persistence where useful.
- Do not weaken validation to make tests pass.
- Do not edit `main` directly.
- Before destructive persistence cleanup, follow `backup/01_BACKUP_AND_ROLLBACK_PLAN.md`.

## High-value current code to preserve/adapt

- `curriculum/teaching_plan/*`
- `application/unit_lesson/realizations.py`
- Print page/PDF machinery
- useful Print prose/table/figure/form logic
- Learn builder persistence/release/runtime/attempt/analytics infrastructure
- retained interaction renderers/evaluators

## High-value current code to replace/delete

- `learn/generation/component_lectio/*`
- ordinary content capability selection in `learn/generation/native_selection.py`
- component-centric LearnDocument shape
- registry-driven ordinary teaching components in `packages/lectio-learn`
- Learn-owned Print helpers
- unsupported video/simulation/media paths
- old compatibility/fallback generation
- package/export tooling whose sole purpose is the retired model

## Execution strategy

Execute phases A through O in order. Each phase file gives:
- active files to open
- tasks
- expected outputs
- acceptance gate

Before editing a listed file, search for all imports/callers/consumers. If the current source differs from this pack, trust the repository and update the phase map before proceeding.

Prefer coherent, testable phase commits. Do not create empty architecture scaffolding without a live consumer.

## Completion definition

The overhaul is not complete until:

```text
fresh Teaching Plan → Learn → editable/reloadable web lesson   PASS
fresh Teaching Plan → Print → reloadable PDF                   PASS
same plan can independently generate the sibling path          PASS
all retained interactions work end to end                      PASS
old ordinary component generation                              GONE
component_lectio active production references                  GONE
Learn-owned Print response helpers                             GONE
unsupported media/video/simulation                             GONE
architecture/domain checks                                     PASS
clean source validation                                        PASS
```

A new instructional intent should normally require zero new ordinary content component classes, zero new ordinary content renderers and zero new ordinary-content schemas. Only a genuinely new learner behavior should require a new interaction contract.
