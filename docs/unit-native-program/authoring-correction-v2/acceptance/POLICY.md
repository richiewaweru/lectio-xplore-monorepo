# Acceptance policy

Every listed gate is mandatory for offline completion. Allowed statuses: NOT_RUN, IN_PROGRESS, PASS, FAIL, BLOCKED. Live tasks are tracked separately as DEFERRED. PASS_WITH_BLOCKERS is not an accepted completed phase state.

A passing gate includes actual command, test reference, tested commit/worktree identity, exit status and durable evidence path. A test count alone proves neither coverage nor quality. Runtime logs and captured payloads must be scrubbed of credentials and personal data. Preserve failed evidence and label mocked inputs/providers explicitly.

For each reviewed defect demonstrate a regression test that fails for the intended reason on pre-fix behavior and passes after the fix, or document an already-landed fix with equivalent evidence. Use an isolated worktree or focused behavior reproduction; never reset the working branch. Do not lower assertions, add expected-failure markers, mark required capabilities unavailable or redesign examples to hide defects.

Tests must use independently specified expectations. Never derive expected correct answers from the output being tested. Mock provider responses may be authored fixtures, but inject them at the provider boundary. Do not inject final documents to claim writer integration. Do not directly edit the database to claim a Builder/API journey. Local component tests are valid offline rendering evidence, not live browser evidence.

Required negative checks include missing definition/input, invalid answer membership, duplicate/dangling IDs, contradictory mappings, non-finite numeric values, unavailable assets, exhausted budgets, unready capabilities, selector escape, repair exhaustion and missing assembly result. Domain-specific validators apply only where relevant.

Actual model quality cannot be proven offline. Record a future live checklist for factual correctness, useful distractors, age appropriateness, coherent prose, accessibility, PDF inspection, student attempts and full UI journeys. No new real-provider or production run is required in this round.

Completion wording: all mandatory gates PASS -> 'Offline corrective gates passed; live/model-quality verification deferred.' Any FAIL/BLOCKED/NOT_RUN -> 'Corrective implementation incomplete' with concrete remaining work. A blocked command is not a test failure, but neither is it a pass. Continue feasible independent tasks. Never silently reinterpret requirements as optional.
