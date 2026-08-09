# 04 — Run 2 (Economics)

**Not started.**

The brief is explicit:

> Do not begin Economics until Science reaches one of: PASS,
> PASS_WITH_EXPORT_FAILURE, PARTIAL_AWAITING_VISUALS caused only by an external
> visual provider.

Science reached none of those. It cleared the structural-planner blocker and
entered execution, but did not reach `ready` or the native viewer, and stopped
short because of the environment issue documented in `05-errors-and-retries.md`
(E1: the backend degrades to all-500s after a few minutes of uptime).

Starting Economics would have spent a second full set of provider calls against
the same unstable environment without adding information — the outstanding
questions are downstream of where Science stopped, and Economics would have
stopped in the same place for the same reason.

No Economics unit, path, lesson, or generation was created in this rerun.

For reference, the Economics unit from the **previous** run remains in the
database from that session:

```text
887c1107-21b3-4be8-9ef1-11e100556067
  "Explain how scarcity forces choices and creates opportunity cost"
  Economics · Grade 8, path v1 APPROVED, 6 lessons
  lesson 887f71be-5a17-470f-8e36-f2a4f3ff9fd0 "Connecting Scarcity to Opportunity Cost"
```

It was left untouched. It is a ready-made starting point for a follow-up run: its
path is already approved, so an Economics attempt could begin directly at lesson
preparation — the step that exercises the fix — without spending another
`path:plan`.
