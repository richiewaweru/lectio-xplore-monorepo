# Refactor Charter

## Goal

Make ownership and maintenance obvious:

- where to look when Print generation breaks,
- where to add a Learn interaction,
- where prompts/writers/validators belong,
- which code is shared infrastructure,
- which code is curriculum semantics,
- which code is legacy and removable.

## Refactor success criterion

A contributor unfamiliar with Xplore history should be able to infer responsibility from the filesystem.

## Current product boundaries

### Curriculum
Shared instructional truth before realization:
- units
- concepts
- misconceptions
- objectives
- paths
- path lessons
- evidence requirements
- teaching plan

### Print
Only exists because paper/PDF exists:
- Page planner
- Page forms
- Print prompts
- Print writers
- Page validation
- Page assembly
- figures/page objects
- PDF/export
- `@lectio/page`

### Learn
Only exists because the interactive product exists:
- Component Lectio generation
- Builder/authoring
- Learn preview/publishing
- student shell
- interactions
- runtime
- classes/distribution
- evidence
- analytics
- `@lectio/learn`

### Platform
Semantically shared infrastructure:
- database session/migrations
- auth primitives
- LLM provider/client
- structured-output plumbing
- retries/backoff
- storage/media primitives
- telemetry/logging
- common jobs/config

## Dependency direction

```text
platform      curriculum
   ↑              ↑
   │              │
   ├──── print ───┤
   └──── learn ───┘
```

Allowed:
- print → curriculum
- print → platform
- learn → curriculum
- learn → platform

Forbidden:
- print → learn
- learn → print
- curriculum → print
- curriculum → learn
- platform → print
- platform → learn
