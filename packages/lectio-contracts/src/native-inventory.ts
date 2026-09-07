/**
 * Native inventory identifiers that must never appear in the shared teaching
 * vocabulary or in any generated teaching view.
 *
 * This list is the machine-checkable half of the teaching/native boundary. It is
 * data, not documentation: `tests/teaching-view.test.ts` and the Learn/Print
 * view tests assert against it. Adding native inventory therefore requires
 * adding it here too, which keeps the guard from silently going stale.
 */

/** Print page object identifiers owned by `@lectio/page`. */
export const PRINT_OBJECT_IDS = [
	'heading',
	'prose',
	'list',
	'table',
	'figure',
	'aside',
	'worked-example',
	'questions',
	'choices',
	'answer-key'
] as const;

/** Learn interaction kind identifiers owned by `@lectio/learn`. */
export const LEARN_INTERACTION_KIND_IDS = [
	'choice',
	'multi-select',
	'fill-blank',
	'numeric',
	'short-response',
	'match-pairs',
	'classify',
	'sequence',
	'image-hotspot',
	'drag-label'
] as const;

/** Learn section component identifiers owned by `@lectio/learn`. */
export const LEARN_COMPONENT_ID_SAMPLE = [
	'quiz-check',
	'fill-in-blank',
	'image-block',
	'video-embed',
	'glossary-inline',
	'simulation-block',
	'worked-example-card',
	'student-textbox',
	'short-answer'
] as const;

/** Keys that carry native schema, capacity or layout detail. */
export const NATIVE_DETAIL_KEYS = [
	'valid_objects',
	'content_schema',
	'payload_schema',
	'payload_schema_ref',
	'capacity',
	'capacity_limits',
	'fragmentation',
	'placement',
	'emphasis',
	'renderer_ref',
	'component_id',
	'component_cards',
	'object_id',
	'section_field',
	'answers',
	'answer_key',
	'correct_option_id',
	'correct_option_ids',
	'examples'
] as const;

/**
 * Identifiers that are legitimately shared vocabulary even though a native path
 * also uses the same string as an inventory id. `classify` and `sequence` are
 * canonical instructional intents and `match-pairs` is a canonical learner
 * action; Learn names interaction kinds after them on purpose rather than
 * inventing a duplicate vocabulary. The boundary rule is about native inventory
 * leaking into teaching, not about banning the words.
 */
export const SHARED_WITH_NATIVE_BY_DESIGN = ['classify', 'sequence', 'match-pairs'] as const;

/** Every native inventory id that shared vocabulary may not name. */
export function nativeInventoryIds(): string[] {
	const shared = new Set<string>(SHARED_WITH_NATIVE_BY_DESIGN);
	return [
		...PRINT_OBJECT_IDS,
		...LEARN_INTERACTION_KIND_IDS,
		...LEARN_COMPONENT_ID_SAMPLE
	].filter((id) => !shared.has(id));
}

/**
 * The subset of native ids that can only ever be an identifier reference.
 *
 * `prose`, `table`, `numeric` and friends are also ordinary English words, so
 * finding them inside a sentence proves nothing. Hyphenated ids such as
 * `worked-example` or `short-response` never occur in natural prose, so a
 * substring hit in free text is a real leak. Views are therefore checked two
 * ways: exact key/value equality against every id in `nativeInventoryIds()`,
 * and free-text search against this narrower set.
 */
export function identifierShapedNativeIds(): string[] {
	return nativeInventoryIds().filter((id) => id.includes('-'));
}
