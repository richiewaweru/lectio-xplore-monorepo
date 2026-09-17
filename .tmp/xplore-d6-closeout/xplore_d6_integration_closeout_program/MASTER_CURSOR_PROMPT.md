# D6 Master Prompt

Workspace: `C:\Projects\lectio`

Before every subphase read all files under `permanent/`, the current phase prompt, prior report, and `docs/d6/D6_STATE.md`.

Rules:
- Test the canonical Unit path only.
- Reuse production services/contracts; do not build parallel test-only flows.
- Use a real test DB.
- Mock only external providers/network boundaries.
- Record failures faithfully.
- Minimal wiring fixes are allowed; product redesign is not.
- Add nontrivial defects to the debt register with canonical owner.
- Stop after every subphase.
