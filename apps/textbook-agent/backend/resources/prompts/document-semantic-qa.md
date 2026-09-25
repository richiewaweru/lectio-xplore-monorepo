# Shared Document Semantic QA

Review the fully assembled SharedLessonDocument after deterministic QA has
passed. Assess whether the document plausibly covers the approved Teaching
Plan progression, learner title and section meaning, task coverage, continuity,
and absence of unsupported pedagogical claims or planning metadata leakage.

Return exactly one closed JSON object:

```json
{
  "status": "pass",
  "issues": []
}
```

Use `status: "issue"` only when a concrete blocking defect remains. Each issue
must use an exact supplied section ID and may cite only node IDs from that
section. Each issue must include a short issue code, explanation, and smallest
required correction. Do not rewrite content, return suggestions, or invent
identities. Treat deterministic checks as authoritative and do not report
their failures again.
