# Pseudocode Diffs

These snippets communicate intent only. Use actual repository models and patterns.

## 1. Skeleton selection

### Before

```python
preview = catalog.preview(...)
slot_roles = [slot.slot_id for slot in preview.variants[0].slots]
# planner receives exact slots
# _build_structural_plan rejects any different roles
```

### Target

```python
preview = catalog.preview(...)
recommended_slots = [slot.slot_id for slot in preview.variants[0].slots]
legal_slots = project_legal_slot_catalog(catalog, objective=lesson.objective)

generated = await run_lesson_flow_planner({
    ...fixed_context,
    "recommended_slots": recommended_slots,
    "legal_slots": legal_slots,
    "hard_constraints": {
        "max_slots": catalog.max_slots,
        "verification_required": True,
    },
})

validate_selected_flow(generated.selected_slots, legal_slots, ...)
slot_instance_ids = assign_slot_instance_ids(generated.selected_slots)
```

## 2. Task source rule

### Before

```python
if action and response_bearing_action(action) and not has_sources:
    errors.append("TEACHING_UNBOUND_RESPONSE_ACTION")
```

### Target

```python
if block.task_mode == "assessment":
    require(response_bearing_action(action))
    require(has_sources)

if block.task_mode == "formative":
    require(response_bearing_action(action))
    forbid(approved_source_ownership_unless_explicitly_promoted)

if has_sources:
    require(block.task_mode == "assessment")
```

Later:

```python
for block in response_blocks:
    shared_task = await author_shared_task(
        block=block,
        sourcebook=sourcebook,
        approved_sources=approved_sources_for(block),
    )
```

## 3. Document writer

```python
refs = bindings.sourcebook_refs_for(block.id)
sourcebook_entries = sourcebook.resolve(refs)

node = await write_document_primitive(
    ...,
    sourcebook_entries=sourcebook_entries,
    immutable_task=shared_task_for(block.id),
)
```

## 4. Learn interaction

### Before

```python
interaction_writer creates prompt/distractors/evaluation
from teaching block + approved source context
```

### Target

```python
interaction = realize_interaction(
    interaction_kind=selected_kind,
    shared_task=task,
    sourcebook=sourcebook,
)

assert_preserves_shared_task(interaction, task)
```

## 5. Print task

```python
treatment = print_treatment_for_learner_action(task.action, intent=block.intent)
page_task = realize_print_task(task=task, treatment=treatment)
assert_preserves_shared_task(page_task, task)
```

## 6. Review

```python
assembled = assemble_path(...)

hard_issues = deterministic_review(
    teaching_plan=plan,
    sourcebook=sourcebook,
    shared_tasks=tasks,
    path_output=assembled,
)

semantic = await semantic_coherence_review(...)
report = merge_reviews(hard_issues, semantic)

if report.repair_required:
    targets = route_repair_targets(report)
    for target in targets:
        repair_one_target(target)
    revalidate()
```
