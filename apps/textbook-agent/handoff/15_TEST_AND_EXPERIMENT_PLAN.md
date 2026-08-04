# Test and Experiment Plan

## A. Defect tests

- unknown role rejected;
- planner receives cognitive jobs;
- unknown StructuralPlan key rejected;
- named legacy field adapted explicitly;
- 0, 1, 2, 3 misconceptions accepted;
- 4 rejected or requires scope split.

## B. Skeleton tests

- every skeleton expands to <=6 slots;
- check present exactly once;
- check never toggled;
- component choices allowed by slot;
- overflow is explicit;
- provenance records exact expansion;
- secondary demand does not silently change skeleton.

## C. Shadow study

Sample: at least 30 real lessons.

Stratify across:

- subject;
- grade;
- knowledge type;
- lesson mode.

Reviewer records:

- current plan preferred;
- skeleton plan preferred;
- equivalent;
- deviation required;
- wrong classification;
- missing slot;
- unnecessary slot.

Promotion criteria should be set before reviewing results.

Suggested initial threshold:

- skeleton preferred/equivalent >=75%;
- wrong classification <=15%;
- unexplained deviation <=20%;
- no severe repeated subject failure.

Thresholds are provisional and must be recorded before analysis.

## D. Path tests

- Grade 4 vs Grade 12 photosynthesis;
- no hard-count truncation;
- prerequisite DAG;
- final evidence covered;
- duplicate concepts flagged;
- teacher edits preserved;
- concept IDs retained across replan.

## E. Bridge tests

- exactly one concept/card;
- path objective unchanged;
- skeleton slots become SectionPlans;
- current review halt works;
- items generated once;
- variant siblings independent;
- QC checks same objective.

## F. Scheduling tests

- group concepts into periods;
- reorder periods without changing path;
- feasibility warnings;
- concepts can span periods only through explicit teacher decision.

## G. Projection tests

- zero model calls for deterministic projections;
- source provenance exact;
- shared diagnostic preserved;
- unit exam coverage report.

## H. Marks tests

- aggregate option counts;
- tagged misconception summaries;
- null distractors remain unclaimed;
- no individual diagnosis from aggregate counts.

## I. Comparative gate

For the same approved objective and context:

```text
Current whole-session planner
vs
Path + skeleton planner
```

Compare:

- objective fidelity;
- prerequisite continuity;
- structural stability;
- teacher edits;
- generation latency;
- QC failures;
- usefulness.

Do not proceed to expensive UI only on aesthetic preference.
