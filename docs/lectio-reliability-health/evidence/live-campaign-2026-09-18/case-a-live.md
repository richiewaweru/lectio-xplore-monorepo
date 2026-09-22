# Case A — sequence/cycle

Status: `PARTIAL`

## Durable identities

- Unit: `bf9441bd-0b8a-4268-a331-682d7801810b` — Cellular Respiration
- Lesson: `4ff3df8e-0042-4486-8902-227387f3f720`
- Preparation: `d15a0cb7-e628-48b4-ba6b-0383435a28da`
- Learn realization: `6881d71c-e858-469e-9504-4256f6a2b0d0`, ready
- Learn output: `learn-out-b0c8013f4942`
- Learn Teaching Plan revision/hash: `1` / `2de2794c07fc4eac57fb58fb9736ebd574c585d27664f08a7831019b48ff6eac`
- Print: ready through the legacy/native path; its recorded plan hash was
  `39d6664314e4b42764e0671bc0f693786ef8897f3a700b2133928d702c5c1832`

## Live result

- Teacher preparation/approval state loaded from durable backend state.
- Learn creation succeeded through the normal UI with the configured real
  provider; the preview rendered 13 nodes and Orient/Explain/Contrast/Check.
- Learn publishing succeeded and the lesson was assigned to the campaign
  class.
- Print preview loaded and teacher/student PDF export actions were completed
  in the UI. The browser did not expose physical PDF files for visual QA.
- Refresh during the asynchronous and plan states reconstructed durable state.

## Shared-plan note

Learn and Print were both admitted from the approved plan, but the legacy Print
row records a different hash than the Learn realization. This is retained as a
provenance follow-up rather than treated as a false match.

## Not completed

The assigned learner instance was created but was not consumed to completion in
this case. Duplicate submission, forged-score rejection, and physical PDF
inspection were not run. Status is therefore partial, not a full PASS.
