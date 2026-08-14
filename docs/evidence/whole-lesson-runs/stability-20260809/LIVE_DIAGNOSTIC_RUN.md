# Live native diagnostic run

Date: 2026-08-09

This report records a failed live run that found real defects. It is deliberately excluded
from targeted proof B and from the four-run final matrix.

## Identity and native entry proof

- Unit: `ac03d8a4-789c-437f-806a-af2fc53af704`
- Path lesson: `0410a02a-36f7-4a04-98de-7cd757d4ea60`
- Generation: `ea292446-abba-40d9-8b5e-6a904fa71653`
- Native whole lesson: `true`
- Document contract: `2`
- Final status/stage: `failed_terminal` / `writing_sections`
- Builder route or record used: no

The authenticated product UI reached structural review, generated approved items, required
teaching review, accepted the teacher approval, completed form planning, and entered parallel
section writing.

## Useful live timing observations

- Item attempt 1 failed after about 119,995 ms.
- Item attempt 2 succeeded after about 99,861 ms.
- Teaching attempt 1 failed after about 129,334 ms with `UnexpectedModelBehavior`.
- Teaching repair succeeded after about 109,237 ms.
- Form planning succeeded after about 25,316 ms.
- One prose writer succeeded after about 21,326 ms.

These timings are observations from the diagnostic run, not final latency acceptance evidence.

## Terminal failure classification

The terminal document recorded mixed causes:

1. Several writer calls failed with `ModelAPIError: Connection error`. At the time of the run,
   these were serialized as `code=UNKNOWN`, `retryable=false`, and terminal block failures.
2. Two `choices` blocks failed with `choices block requires a matching item record id or a
   single options record`.

The generation-level error was `TERMINAL_BLOCK_FAILURE`. Final/candidate reload hashes were
empty, so this run provides no ready-document reload proof.

## Corrections prompted by the run

- Typed provider connection failures now classify as recoverable transport failures.
- Exhausted recoverable writer attempts persist `failed_recoverable`, preserving the native
  retry workflow.
- Empty exception messages retain their error class in telemetry.
- Assessment form planning and assembly are being tightened so a native MCQ source cannot lose
  its item ownership or render as an incompatible page object.
- The terminal row remains immutable. The supported recovery is a new generation through the
  path lesson regeneration route, retaining supersession provenance.

## Exclusion from acceptance

Do not count this generation as a successful run. A fresh generation created after the fixes
must prove recoverable transport handling, exact MCQ binding, ready navigation, visual reload
hashes, and both teacher and student PDF editions.
