import csv

PATH = 'docs/unit-native-program/GATE_RESULTS.csv'
EV = 'docs/unit-native-program/evidence/mocks/p01'
COMMIT = '5a73e31'

ROWS = {
    'P01-K01': (
        'PASS',
        'pnpm exec vitest run tests/regeneration.test.ts (contracts); '
        'pnpm exec vitest run src/lib/catalogue/regeneration.test.ts (page); '
        'pnpm exec vitest run scripts/export-capabilities.test.ts (learn)',
        'Exports regenerate reproducibly and include all intended source metadata; deliberately change a source capability and prove generated selection/writer views update.',
        'Real exporters run in child processes: byte-identical on rerun apart from timestamp; mutated choose_when / capacity / writer guidance reach the generated views; unselectable form drops out; manifest hash moves. 4+5+3 passed, exit 0',
        f'{EV}/k01-contracts-regeneration.txt; {EV}/k01-page-regeneration.txt; {EV}/k01-learn-regeneration.txt',
    ),
    'P01-K02': (
        'PASS',
        'pnpm exec vitest run src/lib/catalogue/views.test.ts (page); '
        'pnpm exec vitest run tests/vocabulary.test.ts (contracts); '
        'pnpm exec vitest run src/lib/learn/capabilities/content.test.ts (learn)',
        'Every supported intent/action ref exists; reverse maps are generated; examples validate against exact schemas.',
        'All 32 intent ids faithful to the Print catalogue; every capability intent/action resolves in @lectio/contracts; object->intents generated and agrees with valid_objects both ways; reference fixture validates under Ajv against the exact per-object payload schemas. 17+7+6 passed, exit 0',
        f'{EV}/k02-page-views.txt; {EV}/k02-contracts-vocabulary.txt; {EV}/k02-learn-content-projection.txt',
    ),
    'P01-K03': (
        'PASS',
        'pnpm exec vitest run src/lib/learn/capabilities/golden.test.ts src/lib/learn/interaction-contract.test.ts',
        'Invalid/duplicate/unknown response IDs and malformed configs fail. Numeric NaN/infinity and negative tolerance rejected.',
        'Unknown/empty/duplicate ids and wrong response counts raise InteractionResponseError; undeclared correct ids and duplicate config ids raise InteractionConfigError; numeric NaN/+-Infinity/negative tolerance rejected at evaluation and through validateInteractionContract; a numeric config on short-response is an authoring error. 43 passed, exit 0',
        f'{EV}/k03-k04-learn-golden.txt',
    ),
    'P01-K04': (
        'PASS',
        'pnpm exec vitest run src/lib/learn/capabilities/golden.test.ts src/lib/learn/interaction-contract.test.ts; '
        'pnpm exec vitest run src/lib/learn/interaction-shells.keyboard.test.ts',
        'Renderer/evaluator golden examples pass for every activated interaction, including partial scoring and attempt limits where supported.',
        'Golden case with stated outcome and score per activated kind; partial scoring proven for multi-select, fill-blank, match-pairs, classify, sequence and cross-checked against the evaluator each record names; attempt limit refuses a third attempt and a retry after correct; unlimited practice honoured; renderer shells evaluate and are keyboard-operable. 43+12 passed, exit 0',
        f'{EV}/k03-k04-learn-golden.txt; {EV}/k04-learn-renderer-goldens.txt',
    ),
    'P01-K05': (
        'PASS',
        'pnpm exec vitest run src/lib/learn/capabilities/consumer-fixture.test.ts',
        'Package-only consumer fixture imports public exports without native source-internal dependencies; incomplete capabilities absent from generation-ready view.',
        'Fixture uses one import site (the published capability entry) to run selection -> writer -> runtime -> scored response; static import-graph walk finds no .svelte dependency; ./capabilities present in the exports map; all 12 incomplete/unavailable/manual-only capabilities absent from the generation-ready selection view and each carries a reason plus a path. 7 passed, exit 0',
        f'{EV}/k05-learn-consumer-fixture.txt',
    ),
    'P01-K06': (
        'PASS',
        'pnpm exec vitest run tests/teaching-view.test.ts (contracts); '
        'pnpm exec vitest run src/lib/learn/capabilities/views.test.ts (learn); '
        'pnpm exec vitest run src/lib/catalogue/views.test.ts (page)',
        'Teaching view contains no native inventory/schema; selection view omits full writer payload contracts.',
        'Shared and Learn teaching views name no page object, component or interaction kind and carry no schema/capacity/answer key; selection views omit payload_schema, field_guidance, examples, negative_cases and every answer-bearing key while keeping purpose, choose/reject and capacity; writer contracts live in a separate view. 9+17+17 passed, exit 0',
        f'{EV}/k06-contracts-teaching-view.txt; {EV}/k06-learn-view-separation.txt; {EV}/k02-page-views.txt',
    ),
}

with open(PATH, encoding='utf-8', newline='') as handle:
    rows = list(csv.reader(handle))

updated = 0
for row in rows:
    if len(row) >= 8 and row[0] == 'P01' and row[1] in ROWS:
        status, command, expected, actual, evidence = ROWS[row[1]]
        row[2] = status
        row[3] = command
        row[4] = expected
        row[5] = actual
        row[6] = evidence
        row[7] = COMMIT
        updated += 1

with open(PATH, 'w', encoding='utf-8', newline='') as handle:
    csv.writer(handle, quoting=csv.QUOTE_ALL, lineterminator='\r\n').writerows(rows)

print(f'updated {updated} P01 rows')
