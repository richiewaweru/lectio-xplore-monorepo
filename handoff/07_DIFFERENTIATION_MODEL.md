# Differentiation Model

## Principle

A variant is an inspectable structural transformation of one canonical lesson.

## Base

```text
Canonical skeleton
+ card-driven misconception slots
+ group toggle
= expanded variant shape
```

## Default profiles

### Support

- retain orientation;
- add or strengthen contrast;
- replace premature independent practice with modelling/guided support;
- preserve shared check.

### Core

- canonical skeleton;
- no structural toggle beyond card-driven misconception slots.

### Extension

- remove orientation when safe;
- add transfer/application;
- preserve shared check.

## Invariant set

All variants share:

- concept ID;
- path objective;
- scope exclusions;
- terminology/notation;
- approved misconceptions;
- shared diagnostic items;
- skeleton family;
- check slot.

## Structural diff UI

```text
SUPPORT              CORE                 EXTENSION
Orient               Orient               Explain
Explain              Explain              Contrast
Contrast             Contrast             Confront
Extra contrast       Confront              Apply
Confront              Check                Check
Check
```

## Toggle schema

```python
VariantToggle:
    id
    label
    operations[]
    priority
    max_slots
    prohibited_targets[]
```

Operations:

- add slot;
- remove slot;
- replace slot;
- duplicate slot;
- change component constraints.

## Overflow behavior

When expanded slots exceed six:

1. apply priority ordering;
2. never remove `check`;
3. never silently drop misconception confrontation;
4. return a visible conflict;
5. require teacher choice or narrower card.

## Voice

Voice remains a rendering/content parameter:

- simple/balanced/formal;
- encouraging/neutral/direct;
- notation.

It is not the primary differentiation mechanism.

## Tests

- check identical across variants;
- objective hash identical;
- prohibited concepts absent;
- exact toggles recorded;
- slot limit conflict visible;
- sibling execution independent.
