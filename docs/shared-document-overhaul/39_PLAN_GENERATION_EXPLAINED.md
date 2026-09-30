# How a lesson plan is made, and why it fails

Written 2026-09-30 after the Convection live run and the planner experiments. This is plain language. Evidence is in `30_RUNBOOK.md` ("Planner quality follow-up").

---

## 1. The flow, step by step

```text
Teacher clicks "Prepare lesson"
│
├─ STEP 1  Structural planner (1 AI call, ~20 s, prompt ≈140 lines)
│          Decides the lesson's shape: skeleton (e.g. orient → explain → contrast → check)
│          and the CONCEPT CARDS. Each card has:
│            • objective        "Explain convection as heat transfer by moving fluid…"
│            • prerequisites    what the learner must already know
│            • misconceptions   M1 "the fluid doesn't need to move"
│                               M2 "convection works in solids too"
│                               M3 "cold fluid rises because cold is lighter"
│          → Teacher reviews the structure.
│
├─ STEP 2  Question writer, once per concept card (1 AI call per card)
│          Writes 5 CHECK QUESTIONS for the card (stem, options, answer key,
│          misconception diagnoses). Convection got:
│            1. pot of water on a stove   2. metal rod in a flame
│            3. room with high/low windows   4. block of ice   5. lava lamp
│          These are frozen: they become the lesson's assessment.
│
├─ STEP 3  Teaching Plan planner (the hard step; prompt ≈475 lines)
│          Input: the structure, the concept card, the 5 frozen questions, and a
│          catalogue of what each lesson section may contain.
│          Output: ONE large structured plan. For every section it gives the
│          blocks (explain, model, surface misconception, practise…), each
│          block's purpose and brief, which frozen question is checked where,
│          what the learner must be able to do on exit, and the bridges between sections.
│          │
│          ├─ Code validation (~30 rules): block counts per section, allowed
│          │  block types per section, every question used exactly once, IDs copied exactly…
│          │
│          └─ AI reviewer (prompt ≈76 lines): judges meaning. Is each outcome
│             taught? Is each misconception shown failing? Does any teaching
│             block reuse a check question's scenario (answer leakage)? Is anything factually wrong?
│
│          If either rejects the plan, the planner gets ONE more try with the
│          rejection notes. If that also fails, the job fails. The job system
│          allows up to 3 of these rounds.
│
├─ STEP 4  Teacher approves the plan (locked by hash).
│
└─ STEP 5  Lesson document → Learn → Print. These have been reliable.
```

## 2. What actually fails (22 planner runs on Convection)
7 passed and 15 failed. Every success needed the second try.

| Why it was rejected | Times | Plain meaning |
|---|---|---|
| Reused a check question's scenario | 8 | It taught with "a pot of water on a stove", which question 1 already asks about, so it handed over the answer. |
| Broke a structural rule | 3 | Too many blocks in a section, or an unusual block type without the required reason. |
| Content gap | 2 | An outcome was not taught, or a misconception was raised but never shown failing. |
| Technical | 2 | Output was cut off (with "medium" thinking); the reviewer itself errored once. |

## 3. Are we hamstringing DeepSeek?
Partly yes, but not mainly through "too many rules". There are three separate issues.

**a) We are asking the fast, cheap model to do the hardest job.**
- Every tier in the local config (fast, standard, premium) points to **`deepseek-flash`**, including the Teaching Plan planner and its reviewer.
- In August the planner ran on **`deepseek-v4-pro`**. Those runs passed, but the rules were lighter then, so the comparison is not clean.
- Flash is built for speed. Planning a whole lesson under 475 lines of constraints is the most demanding reasoning task in the pipeline. The data cannot yet say how much of the failure rate comes from this.
- It is the cheapest thing to test: rerun the same experiment with the planner on the pro model.

**b) The flow sets the model up to fail on the most common error.**
- The question writer runs first and uses the best textbook examples.
- The planner is then told, "teach convection, but you may not use any of those examples".
- The most natural teaching example has already been spent on a check question. Any model will tend to reach for it. The reviewer is right to reject that: teaching with the pot and then asking about the pot gives away the answer.
- This is a design-order problem, not a model-capability problem.

**c) One all-or-nothing answer.**
- The plan is written in one go, and any single rule broken anywhere rejects the whole plan.
- The model then gets one repair attempt.
- Mechanical rules, such as block counts, are checked only after a full 3–6 minute generation and review, so a trivial slip costs a whole round.

**What is *not* the problem:** the rules themselves are mostly good. They are what stop a lesson from leaking answers, leaving misconceptions uncorrected, or containing factual errors. Removing them would raise the pass rate and lower lesson quality.

## 4. Changes made so far
- **Planner thinking lowered from "medium" to "low"** (commit `efe39b30`). "Medium" burned 36k+ thinking tokens per call and cut its own output off. Pass rates by setting:
  - off: 0/3
  - low: 3/5
  - medium: 1/3
- **Reserved-scenario list added.** The planner now receives a short list of the check questions' scenarios, with an instruction to choose its teaching examples from outside that list. It helps, but the planner still sometimes reaches for the pot.
- **Reviewer thinking kept at "medium".** "Low" was faster but converged less often (2/5 versus 3/5).

## 5. Recommended next steps, cheapest first
1. **Test the pro model for the planner and reviewer.** This is one config change plus a 5-run A/B, and it answers question 3a directly.
2. **Reserve a teaching example before the questions are written.** The structural step (or the question writer) chooses a "running teaching case" for the lesson, and the question writer must not use it. This removes the biggest failure at its source.
3. **Add instant code checks before the AI reviewer.** Block limits, required reasons and obvious scenario overlap would be caught in seconds, with a targeted fix sent back, instead of costing a full round.
4. **Human quality read of one finished lesson (Convection)** to confirm that a passing plan also produces a good lesson.
