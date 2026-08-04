/** Page objects — physical document forms. */
export const PAGE_OBJECTS = [
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

export type PageObject = (typeof PAGE_OBJECTS)[number];

/** Pedagogical intents — teaching jobs. */
export const INTENT_IDS = [
	'orient',
	'activate-prior-knowledge',
	'state-goal',
	'define',
	'name-parts',
	'classify',
	'compare',
	'sequence',
	'explain',
	'explain-cause',
	'trace-flow',
	'show-structure',
	'demonstrate',
	'model-thinking',
	'derive',
	'interpret',
	'apply',
	'transfer',
	'practise-guided',
	'practise-independent',
	'check-understanding',
	'diagnose-misconception',
	'warn',
	'emphasise',
	'memory-aid',
	'summarise',
	'connect-forward',
	'connect-back',
	'reflect',
	'investigate',
	'evaluate',
	'answer-key'
] as const;

export type IntentId = (typeof INTENT_IDS)[number];
