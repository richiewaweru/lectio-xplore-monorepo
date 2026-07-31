# Risks, Non-Goals, and Stop Rules

## Highest-risk assumption

Deterministic skeletons may encode premature pedagogical rigidity.

Mitigation:

- shadow mode;
- reviewer data;
- deviations;
- versioned YAML;
- explicit promotion gate.

## Silent failures to guard

- path looks complete but omits prerequisite;
- canonical concept accidentally duplicated;
- path and lesson objectives drift;
- variant changes more than declared;
- skeleton toggle silently drops a misconception slot;
- factual fragment becomes useless standalone lesson;
- plan says prerequisite established while teaching actual says otherwise;
- resource projection omits necessary context;
- aggregate marks overstate individual misconceptions;
- legacy adapter swallows unknown fields.

## Non-goals

- learner accounts;
- adaptive routing;
- AI tutor;
- knowledge tracing;
- A/B assignment;
- microservices;
- marketplace;
- replacing Lectio;
- replacing Builder;
- replacing PDF generation.

## Stop rules for implementation agent

Stop and report when:

1. a destructive migration appears necessary;
2. existing item-wall or shared-item invariants would break;
3. a proposed skeleton cannot fit six slots without silent loss;
4. path-planned lesson performs materially worse at the validation gate;
5. shadow data contradicts taxonomy;
6. repository behavior contradicts this handoff and no safe adapter exists;
7. live credentials are required.

Do not stop for ordinary naming or file-placement decisions that repository conventions resolve.
