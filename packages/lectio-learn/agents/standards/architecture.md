# Architecture

Rules for respecting and maintaining architectural boundaries. These apply regardless of which architecture pattern a project uses (DDD, clean architecture, hexagonal, microservices, or anything else).

## Respect the Declared Boundaries

- Every project declares its architectural rules in `agents/project.md`. Read them before writing code.
- Never introduce a dependency that violates the declared layer/module boundaries. This is not optional and not something to "fix later."
- If you're unsure whether an import is allowed, check the rules. If the rules don't cover your case, ask before proceeding.

## Dependency Direction

- Dependencies should flow in one direction: from outer layers toward inner layers, from consumers toward providers, from specific toward general.
- Core business logic should never depend on delivery mechanisms (HTTP, CLI, message queues) or infrastructure (databases, file systems, external APIs).
- This principle applies regardless of terminology. Whether you call it "domain," "core," "model," or "business" -- the rule is the same: the innermost layer is self-contained.

## When to Add a New Module or Package

Add a new module when:
- You have a genuinely distinct concern that doesn't fit existing modules
- The new module has a clear, single responsibility
- You can describe what it owns in one sentence

Don't add a new module when:
- You're just organizing a few helper functions (put them in the nearest relevant module)
- You're creating a wrapper that adds no value over calling the wrapped thing directly
- You're "preparing for future growth" that hasn't materialized

## When to Introduce an Abstraction

Add an abstraction (interface, protocol, port, adapter) when:
- You need to swap implementations (e.g., different LLM providers, test doubles for external services)
- You need to enforce a dependency boundary (outer layers depend on an abstraction, inner layers define it)
- Multiple consumers need the same contract

Don't add an abstraction when:
- There's only one implementation and no realistic prospect of another
- You're adding it "for testability" but could test through the real code path
- The abstraction just mirrors the concrete class 1:1

## Structural Changes Require Extra Care

If your change modifies architectural boundaries (moves code between layers, introduces new modules, changes dependency direction):

1. Explicitly call out the structural change in your PR description
2. Verify no new boundary violations were introduced
3. Update `agents/project.md` if the architecture rules changed
4. Consider whether the change should be in its own PR, separate from behavioral changes

## Anti-Patterns

- **God module**: One module that everything depends on. Break it up by responsibility.
- **Circular dependencies**: A imports B which imports A. Fix the design -- extract the shared concept.
- **Leaky abstraction**: Infrastructure details (SQL, HTTP, file paths) appearing in business logic. Push them to the outer layer.
- **Shotgun surgery**: A single logical change requiring edits across many unrelated modules. The boundaries might be in the wrong place.

## Pragmatism

- Architecture rules exist to keep the codebase maintainable at scale. They're not ceremonial.
- If a rule is consistently getting in the way of real work, the rule might need updating -- raise it rather than working around it.
- Perfect architecture with no shipped features is worth nothing. Ship first, refactor when friction justifies it.
