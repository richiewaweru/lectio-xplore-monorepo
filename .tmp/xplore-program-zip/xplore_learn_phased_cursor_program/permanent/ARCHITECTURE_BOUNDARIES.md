# Architecture Boundaries

## Domains

### Authoring
Owns:
- units
- concepts
- misconceptions
- objectives
- evidence requirements
- path/lesson structure
- teaching plan
- teacher approval

Must remain realization-neutral.

### Print
Owns:
- page planner
- page forms
- page writers
- page validation
- page assembly
- `@lectio/page`
- PDF

Must not depend on Learn/runtime/distribution.

### Learn
Owns:
- web-native component schemas
- component registry
- interaction contracts
- evaluation contracts
- narration/accessibility capabilities
- responsive component rendering
- LearnDocument realization

### Distribution
Owns:
- classes
- class teacher memberships
- learner enrollments
- invites
- assignments
- assignment recipients
- rolling audience semantics

### Runtime
Owns:
- LearningInstance execution
- sessions
- attempts
- answer evaluation
- retries/hints/feedback
- resume
- section/node completion

Runtime does not own classes or assignments.

### Evidence / Analytics
Owns:
- attempt→concept evidence
- misconception evidence
- lesson progress projections
- concept-state projections
- role-specific teacher/student analytics

## Dependency direction

```text
instructional core
   /        \
Print      Learn
             ↓
        Distribution
             ↓
          Runtime
             ↓
          Evidence
             ↓
          Insight
```

Forbidden:
- Print importing Learn.
- Learn importing Print.
- Runtime importing teacher dashboard/UI modules.
- Learn component definitions persisting learner attempts.
- Analytics mutating raw attempts.
- Assignments pointing to mutable lesson drafts.
