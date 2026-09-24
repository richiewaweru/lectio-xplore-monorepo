# Architecture Guards

Enforce:

```text
document/   ✗ imports learn/
document/   ✗ imports print/

curriculum/ ✗ imports learn/
curriculum/ ✗ imports print/

infra/      ✗ imports product-domain logic
```

After cutover:
- only SharedDocument generation may invoke Section Composer/Writer;
- Learn ordinary authoring calls = 0;
- Print ordinary authoring calls = 0.

Contract guards:
- approved Teaching Plan hash cannot mutate;
- SharedDocument consumers reject hash mismatch;
- TaskAnchor registry is complete;
- writer cannot alter composition shape;
- path realization cannot widen task capability set.

Deleted modules/routes should be absent and guarded against reintroduction.
