import { CONFIG_SCHEMAS, RESPONSE_SCHEMAS } from './schemas';
import type { LearnCapabilityRecord } from './types';

const CONTRACT_VERSION = '1.0.0';
const SOURCE_DIR = 'packages/lectio-learn/src/lib/learn';
const EVALUATOR = 'packages/lectio-learn/src/lib/learn/interaction-contract.ts';

/**
 * Every text/auto-score interaction below has a closed payload schema, a
 * deterministic evaluator, a keyboard-operable renderer and — from this phase —
 * a contract export. None of them is wired into native selection yet, so none
 * claims `generation-ready`: readiness is `planned` with `availability:
 * incomplete` and a stated path. Claiming otherwise would make a UI shell look
 * like a generation capability.
 */
const NOT_YET_SELECTABLE: Pick<
	LearnCapabilityRecord,
	'readiness' | 'availability' | 'blocking_reasons' | 'path_to_readiness'
> = {
	readiness: 'planned',
	availability: 'incomplete',
	blocking_reasons: [
		'No native selection policy offers this kind, so no generation run can choose it (P04).',
		'No Builder editor exists for the payload, so a teacher cannot repair a generated instance (P06).'
	],
	path_to_readiness: [
		'P04: register the kind in the native selection policy and prove selection from a shared plan.',
		'P06: add a Builder editor for the payload and prove an edit persists and republishes.',
		'P07: prove attempt persistence and authoritative evaluation through the runtime.'
	]
};

const SPATIAL_BLOCKING = [
	'No coordinate authoring tool exists: region and target positions cannot be produced for a real asset.',
	'No asset-region model binds a figure asset to named regions, so regions cannot be verified against the image.'
];

const SPATIAL_PATH = [
	'Define an asset-region authoring model that binds an existing asset id to named regions with a declared coordinate system.',
	'Build the authoring surface that produces those regions from a real asset, and validate them against the asset box.',
	'P04/P06: register the kind for selection and repair only once authored regions are verifiable.'
];

function accessibility(notes: string) {
	return { keyboard_operable: true, narration: 'optional' as const, notes };
}

export const interactionCapabilities: LearnCapabilityRecord[] = [
	{
		id: 'choice',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Let a learner choose the one correct option from a closed set.',
		cognitive_job: 'discriminate the correct idea from plausible alternatives',
		supported_intents: ['check-understanding', 'diagnose-misconception', 'practise-independent'],
		supported_actions: ['select-one'],
		choose_when:
			'The response reduces to one option, and every wrong option is one a real learner would pick for a stateable reason.',
		reject_when:
			'Distractors are filler, more than one option is defensible, or the answer cannot be reduced to a selection.',
		prerequisites: ['The idea being checked has already been taught in this lesson.'],
		requires: [
			'at least two options with unique non-empty ids',
			'exactly one correct_option_id, and it must name a declared option',
			'keyboard-operable option selection'
		],
		capacity: { optionsMin: 2, optionsMax: 5, stemMaxWords: 40, optionMaxWords: 20 },
		payload_schema_ref: 'learn/choice/config.v1',
		payload_schema: CONFIG_SCHEMAS.choice!,
		field_guidance: {
			options:
				'Stable ids, parallel grammatical form. Give each wrong option an explanation naming the misconception it reveals.',
			correct_option_id: 'Must equal the id of exactly one declared option.',
			presentation:
				"'image' renders options as pictures; evaluation is identical, so do not author a separate kind for it."
		},
		examples: [
			{
				options: [
					{ id: 'soil', text: 'From the soil', explanation: 'Mass is not drawn from soil.' },
					{ id: 'air', text: 'From carbon dioxide in the air' },
					{ id: 'light', text: 'From sunlight alone', explanation: 'Light supplies energy, not mass.' }
				],
				correct_option_id: 'air'
			}
		],
		negative_cases: [
			'a single option',
			'duplicate option ids',
			'correct_option_id naming an option that is not declared',
			'a distractor no learner would choose'
		],
		renderer_ref: `${SOURCE_DIR}/ChoiceInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS.choice!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateChoice`,
			partial_scoring: false,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			presentation: "text (default) or image; a consumer may narrow but not add a variant",
			attempt_policy: 'consumer may lower max_attempts within the declared default'
		},
		default_behaviour: {
			max_attempts: 2,
			show_feedback_after_submit: true,
			allow_retry_after_correct: false
		},
		asset_requirements: null,
		accessibility: accessibility(
			'Options are a radio group; correctness feedback is announced through a status region.'
		),
		presentation_variants: ['text', 'image'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/ChoiceInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence:
				'interaction-contract.test.ts, capabilities/golden.test.ts, interaction-shells.keyboard.test.ts'
		},
		compatibility: {
			since: '0.7.0',
			deprecates: ['image-choice as a separate kind'],
			migration: "Author image options as choice with presentation: 'image'."
		}
	},
	{
		id: 'multi-select',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Let a learner choose every option that satisfies the prompt.',
		cognitive_job: 'apply a membership rule across several candidates',
		supported_intents: ['check-understanding', 'classify', 'practise-independent'],
		supported_actions: ['select-many'],
		choose_when:
			'More than one option is correct and the learner must find all of them without being told how many.',
		reject_when:
			'Exactly one option is correct, or the options are not independent of each other.',
		prerequisites: ['The membership rule has been stated or derived in this lesson.'],
		requires: [
			'at least two options with unique non-empty ids',
			'every correct_option_id must name a declared option',
			'no duplicate ids in the learner response'
		],
		capacity: { optionsMin: 3, optionsMax: 6, correctMin: 2, stemMaxWords: 40 },
		payload_schema_ref: 'learn/multi-select/config.v1',
		payload_schema: CONFIG_SCHEMAS['multi-select']!,
		field_guidance: {
			options: 'Independent candidates. Do not include an option that implies another.',
			correct_option_ids:
				'Two or more declared option ids. A single correct id belongs to the choice kind instead.'
		},
		examples: [
			{
				options: [
					{ id: 'co2', text: 'Carbon dioxide' },
					{ id: 'water', text: 'Water' },
					{ id: 'glucose', text: 'Glucose' },
					{ id: 'oxygen', text: 'Oxygen' }
				],
				correct_option_ids: ['co2', 'water']
			}
		],
		negative_cases: [
			'only one correct option',
			'duplicate selected ids in a response',
			'a selected id that is not a declared option'
		],
		renderer_ref: `${SOURCE_DIR}/MultiSelectInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS['multi-select']!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateMultiSelect`,
			partial_scoring: true,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			attempt_policy: 'consumer may lower max_attempts within the declared default'
		},
		default_behaviour: {
			max_attempts: 2,
			show_feedback_after_submit: true,
			allow_retry_after_correct: false,
			scoring: 'hits minus false positives, floored at zero'
		},
		asset_requirements: null,
		accessibility: accessibility('Checkbox group with an announced running selection count.'),
		presentation_variants: ['text'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/MultiSelectInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence: 'capabilities/golden.test.ts, interaction-contract.test.ts'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	},
	{
		id: 'fill-blank',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Have a learner supply the missing terms inside a given structure.',
		cognitive_job: 'retrieve precise vocabulary in context',
		supported_intents: ['check-understanding', 'practise-guided', 'define'],
		supported_actions: ['complete-missing-values'],
		choose_when:
			'The surrounding text supplies enough context that the missing term is determinate, and the accepted answers can be enumerated.',
		reject_when:
			'The answer is a judgement, a sentence, or has more valid phrasings than can be listed.',
		prerequisites: ['The terms being recalled appear earlier in the lesson.'],
		requires: [
			'one accepted-answer entry per blank',
			'blank_ids, when present, must be unique and match the answer count',
			'the response must carry exactly one value per blank'
		],
		capacity: { blanksMin: 1, blanksMax: 6, alternativesPerBlankMax: 5 },
		payload_schema_ref: 'learn/fill-blank/config.v1',
		payload_schema: CONFIG_SCHEMAS['fill-blank']!,
		field_guidance: {
			answers:
				'One entry per blank, in reading order. Use an array for a blank with genuine alternatives.',
			blank_ids: 'Stable ids so per-blank feedback survives a re-render.',
			case_sensitive:
				'Leave false unless capitalisation is the thing being assessed. Answers are compared after trimming and whitespace collapsing.'
		},
		examples: [
			{
				answers: [['CO2', 'carbon dioxide'], 'water'],
				blank_ids: ['blank-1', 'blank-2']
			}
		],
		negative_cases: [
			'no blanks',
			'a blank whose accepted answer is empty',
			'a response with fewer values than declared blanks',
			'duplicate blank_ids'
		],
		renderer_ref: 'packages/lectio-learn/src/lib/components/lectio/FillInTheBlank.svelte',
		response_schema: RESPONSE_SCHEMAS['fill-blank']!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateFillBlank`,
			partial_scoring: true,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			case_sensitive: 'consumer may enable exact-case comparison',
			attempt_policy: 'unlimited by default in practice mode'
		},
		default_behaviour: {
			max_attempts: null,
			show_feedback_after_submit: true,
			allow_retry_after_correct: true,
			normalization: 'trim, collapse internal whitespace, case-fold unless case_sensitive'
		},
		asset_requirements: null,
		accessibility: accessibility('Each blank is a labelled text input with per-blank feedback.'),
		presentation_variants: ['text'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/interaction-contract.ts#evaluateFillBlank`,
			data_schema: true,
			evaluator: true,
			authoring_support: true,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence: 'capabilities/golden.test.ts; the fill-in-blank content capability is selectable'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	},
	{
		id: 'numeric',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Collect a numeric answer and score it within a declared tolerance.',
		cognitive_job: 'carry out a calculation and report a value',
		supported_intents: ['apply', 'practise-guided', 'practise-independent', 'check-understanding'],
		supported_actions: ['enter-number'],
		choose_when:
			'The answer is a single number, and the acceptable spread around it can be stated as a tolerance.',
		reject_when:
			'The answer is a range, a symbolic expression, or depends on the method the learner chose.',
		prerequisites: ['The method producing the value has been demonstrated or derived.'],
		requires: [
			'a finite target value',
			'a non-negative finite tolerance when tolerance is given',
			'a finite numeric response'
		],
		capacity: { promptMaxWords: 60 },
		payload_schema_ref: 'learn/numeric/config.v1',
		payload_schema: CONFIG_SCHEMAS.numeric!,
		field_guidance: {
			value: 'The exact expected value. NaN and infinity are rejected.',
			tolerance:
				'Absolute tolerance, never negative. Use 0 for an exact answer; do not use tolerance to hide an unclear question.',
			unit:
				'State the unit the learner should answer in. The evaluator compares magnitudes only; it does not convert units.'
		},
		examples: [{ value: 42, tolerance: 0 }, { value: 9.81, tolerance: 0.05, unit: 'm/s^2' }],
		negative_cases: [
			'value: NaN',
			'value: Infinity',
			'tolerance: -1',
			'a non-numeric or non-finite response'
		],
		renderer_ref: `${SOURCE_DIR}/NumericInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS.numeric!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateNumeric`,
			partial_scoring: false,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			tolerance: 'consumer may tighten but not widen beyond the authored value',
			unit: 'consumer may not change the declared unit'
		},
		default_behaviour: {
			max_attempts: 2,
			show_feedback_after_submit: true,
			allow_retry_after_correct: false,
			units_policy: 'declared for the learner; not converted by the evaluator'
		},
		asset_requirements: null,
		accessibility: accessibility('Single labelled numeric input; unit shown beside the field.'),
		presentation_variants: ['text'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/NumericInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence: 'capabilities/golden.test.ts negative numeric cases'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	},
	{
		id: 'short-response',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose:
			'Collect a short written answer, scored against declared accepted answers or read by a teacher.',
		cognitive_job: 'produce an answer in the learner’s own words',
		supported_intents: ['check-understanding', 'reflect', 'evaluate', 'explain'],
		supported_actions: ['enter-text', 'produce-extended-response'],
		choose_when:
			'The learner must write the answer. Use accepted-answers only when the correct wordings can genuinely be listed; otherwise use teacher-review.',
		reject_when:
			'The answer is open reasoning and the author wants it auto-scored anyway. String matching is not comprehension.',
		prerequisites: ['A teacher review surface exists when evaluation is teacher-review.'],
		requires: [
			"evaluation must be 'accepted-answers' or 'teacher-review'",
			'accepted-answers mode requires a non-empty, normalization-unique accepted_answers list',
			'teacher-review mode must not complete on correctness'
		],
		capacity: { promptMaxWords: 60, acceptedAnswersMax: 12, responseMaxWords: 60 },
		payload_schema_ref: 'learn/short-response/config.v1',
		payload_schema: CONFIG_SCHEMAS['short-response']!,
		field_guidance: {
			evaluation:
				"'accepted-answers' for a term, name or short phrase. 'teacher-review' for anything the learner reasons out.",
			accepted_answers:
				'Every wording that should score as correct, including common synonyms. Compared after trimming, whitespace collapsing and case folding.',
			review_guidance: 'What the teacher should look for. Only meaningful under teacher-review.',
			case_sensitive: 'Enable only when capitalisation is itself the answer.',
			max_words:
				'Advisory ceiling shown to the learner. It bounds the input, it does not affect scoring.'
		},
		examples: [
			{ evaluation: 'accepted-answers', accepted_answers: ['CO2', 'carbon dioxide'] },
			{
				evaluation: 'teacher-review',
				review_guidance: 'Look for a stated mechanism linking light energy to glucose.'
			}
		],
		negative_cases: [
			'evaluation omitted',
			'a numeric value supplied instead of text semantics',
			'accepted-answers mode with an empty accepted_answers list',
			'accepted answers that collide after normalization',
			"teacher-review paired with completion { type: 'correct' }"
		],
		renderer_ref: `${SOURCE_DIR}/ShortResponseInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS['short-response']!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateShortResponse`,
			partial_scoring: false,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			evaluation: 'consumer may switch to teacher-review, never the reverse',
			accepted_answers: 'consumer may add accepted wordings, never remove the authored ones'
		},
		default_behaviour: {
			max_attempts: 2,
			teacher_review_outcome: 'pending-review with zero earned score',
			normalization: 'trim, collapse internal whitespace, case-fold unless case_sensitive'
		},
		asset_requirements: null,
		accessibility: accessibility(
			'Single labelled text input; review-pending state is announced rather than shown as a score.'
		),
		presentation_variants: ['text'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/ShortResponseInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence:
				'capabilities/golden.test.ts short-response cases; the numeric alias defect is gone'
		},
		compatibility: {
			since: '0.7.0',
			deprecates: ['short-response evaluated through the numeric evaluator'],
			migration:
				"Replace { value, tolerance } with { evaluation: 'accepted-answers', accepted_answers: [...] } or { evaluation: 'teacher-review' }."
		}
	},
	{
		id: 'match-pairs',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Have a learner connect each item to its counterpart.',
		cognitive_job: 'recognise correspondence between two sets',
		supported_intents: ['define', 'name-parts', 'check-understanding', 'practise-guided'],
		supported_actions: ['match-pairs'],
		choose_when:
			'Each item has exactly one counterpart, and the correspondence is the thing being learned.',
		reject_when:
			'An item has several valid counterparts, or the sets are so small the answer is obvious by elimination.',
		prerequisites: ['Both sides have been introduced in the lesson.'],
		requires: [
			'unique source ids',
			'every submitted link must reference a declared source and a declared target',
			'no source may be submitted twice'
		],
		capacity: { pairsMin: 3, pairsMax: 8, labelMaxWords: 12 },
		payload_schema_ref: 'learn/match-pairs/config.v1',
		payload_schema: CONFIG_SCHEMAS['match-pairs']!,
		field_guidance: {
			pairs:
				'Each entry links one source id to one target id. Source ids must be unique; a repeated source has no single answer.'
		},
		examples: [
			{
				pairs: [
					{ left: 'chloroplast', right: 'captures light' },
					{ left: 'stomata', right: 'exchanges gas' },
					{ left: 'root-hair', right: 'absorbs water' }
				]
			}
		],
		negative_cases: [
			'duplicate source ids in the config',
			'the same source submitted twice',
			'a link naming a target that is not declared'
		],
		renderer_ref: `${SOURCE_DIR}/MatchPairsInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS['match-pairs']!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateMatchPairs`,
			partial_scoring: true,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			attempt_policy: 'consumer may lower max_attempts within the declared default'
		},
		default_behaviour: {
			max_attempts: 2,
			show_feedback_after_submit: true,
			allow_retry_after_correct: false,
			scoring: 'one point per correct link'
		},
		asset_requirements: null,
		accessibility: accessibility(
			'Two button lists; a source is activated then a target, so no pointer drag is required.'
		),
		presentation_variants: ['text'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/MatchPairsInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence: 'capabilities/golden.test.ts, interaction-shells.keyboard.test.ts'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	},
	{
		id: 'classify',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Have a learner assign each item to exactly one named category.',
		cognitive_job: 'apply a category membership rule',
		supported_intents: ['classify', 'check-understanding', 'practise-guided'],
		supported_actions: ['classify-items'],
		choose_when:
			'Every item belongs to exactly one category and the membership rule has been stated.',
		reject_when:
			'An item legitimately belongs to more than one category. Multiple-category membership is not implemented, so it must not be authored.',
		prerequisites: ['The categories and their membership rule appear in the lesson.'],
		requires: [
			'single-category membership per item',
			'unique item ids',
			'every submitted assignment must name a declared item and a declared category'
		],
		capacity: { itemsMin: 3, itemsMax: 10, categoriesMin: 2, categoriesMax: 4 },
		payload_schema_ref: 'learn/classify/config.v1',
		payload_schema: CONFIG_SCHEMAS.classify!,
		field_guidance: {
			pairs:
				'One entry per item: `left` is the item id, `right` is its single category id. The evaluator scores one point per correct assignment.',
			categories: 'Declare the category ids and labels the learner chooses between.'
		},
		examples: [
			{
				categories: [
					{ id: 'reactant', label: 'Reactant' },
					{ id: 'product', label: 'Product' }
				],
				pairs: [
					{ left: 'co2', right: 'reactant' },
					{ left: 'water', right: 'reactant' },
					{ left: 'glucose', right: 'product' }
				]
			}
		],
		negative_cases: [
			'an item assigned to two categories',
			'duplicate item ids',
			'an assignment naming an undeclared category'
		],
		renderer_ref: `${SOURCE_DIR}/ClassifyInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS.classify!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateMatchPairs`,
			partial_scoring: true,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			categories_per_item: 'one only; a consumer may not enable multiple-category membership'
		},
		default_behaviour: {
			max_attempts: 2,
			categories_per_item: 1,
			scoring: 'one point per correctly categorised item'
		},
		asset_requirements: null,
		accessibility: accessibility(
			'Item and category buttons; an item is activated then a category, so no pointer drag is required.'
		),
		presentation_variants: ['text'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/ClassifyInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence:
				'capabilities/golden.test.ts asserts single-category evaluation matches the declaration'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	},
	{
		id: 'sequence',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Let a learner reconstruct a defensible order.',
		cognitive_job: 'reconstruct temporal or procedural order',
		supported_intents: ['sequence', 'practise-guided', 'check-understanding'],
		supported_actions: ['order-items'],
		choose_when:
			'The stages have one defensible order and every stage is distinguishable from the others.',
		reject_when:
			'Several orders are valid. Only one accepted order is implemented, so alternatives must not be claimed.',
		prerequisites: ['The process has been shown or traced in the lesson.'],
		requires: [
			'unique item ids',
			'the expected order must cover every item exactly once',
			'the response must be a permutation of the declared items'
		],
		capacity: { itemsMin: 3, itemsMax: 7, labelMaxWords: 12 },
		payload_schema_ref: 'learn/sequence/config.v1',
		payload_schema: CONFIG_SCHEMAS.sequence!,
		field_guidance: {
			order: 'The one accepted order, as item ids. Alternative valid orders are not supported.',
			items: 'Labels shown to the learner, keyed by the same ids used in `order`.'
		},
		examples: [
			{
				items: [
					{ id: 'absorb', label: 'Light is absorbed' },
					{ id: 'split', label: 'Water is split' },
					{ id: 'fix', label: 'Carbon is fixed' }
				],
				order: ['absorb', 'split', 'fix']
			}
		],
		negative_cases: [
			'duplicate item ids',
			'a response shorter than the declared order',
			'a response containing an item that is not declared',
			'claiming several accepted orders'
		],
		renderer_ref: `${SOURCE_DIR}/SequenceInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS.sequence!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateSequence`,
			partial_scoring: true,
			invalid_response_policy: 'reject'
		},
		allowed_config: {
			accepted_orders: 'exactly one; a consumer may not declare alternatives'
		},
		default_behaviour: {
			max_attempts: null,
			scoring: 'one point per item in its expected position',
			accepted_orders: 1
		},
		asset_requirements: null,
		accessibility: accessibility(
			'Move-up and move-down buttons per item, so ordering never requires a pointer drag.'
		),
		presentation_variants: ['text'],
		...NOT_YET_SELECTABLE,
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/SequenceInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence: 'capabilities/golden.test.ts partial-order case'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	},
	{
		id: 'image-hotspot',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Have a learner identify the correct region of a given visual.',
		cognitive_job: 'locate a named structure on a representation',
		supported_intents: ['name-parts', 'show-structure', 'check-understanding'],
		supported_actions: ['identify-region'],
		choose_when:
			'Not yet. The location is the answer, but no authoring path produces verified regions for a real asset.',
		reject_when:
			'Always, for generated content: regions cannot be guessed from an unrelated image, and none can currently be authored.',
		prerequisites: [
			'An asset-region authoring model that binds an existing asset id to named regions.',
			'A verified keyboard path to every region.'
		],
		requires: [
			'an existing asset id with alt text',
			'at least two regions with unique ids and coordinates inside the asset box',
			'correct_option_id naming a declared region'
		],
		capacity: { regionsMin: 2, regionsMax: 8, labelMaxWords: 8 },
		payload_schema_ref: 'learn/image-hotspot/config.v1',
		payload_schema: CONFIG_SCHEMAS['image-hotspot']!,
		field_guidance: {
			image: 'Reference an asset that already exists. Never describe an image that was not produced.',
			regions:
				'Percentages of the asset’s intrinsic box, origin top-left. Coordinates must be verified against the actual asset, not estimated.',
			correct_option_id: 'Must name one declared region.'
		},
		examples: [],
		negative_cases: [
			'regions estimated from an unrelated image',
			'no asset id',
			'duplicate region ids',
			'correct_option_id naming an undeclared region'
		],
		renderer_ref: `${SOURCE_DIR}/ImageHotspotInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS['image-hotspot']!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateChoice`,
			partial_scoring: false,
			invalid_response_policy: 'reject'
		},
		allowed_config: {},
		default_behaviour: { max_attempts: 2 },
		asset_requirements: {
			kinds: ['image', 'svg'],
			identity: 'An existing asset id. An unresolved asset is a tracked dependency, not a blank render.',
			coordinate_system: 'percentage of intrinsic asset box, origin top-left',
			authoring_tool: null
		},
		accessibility: accessibility(
			'Regions are focusable buttons in reading order, proven by interaction-shells.keyboard.test.ts.'
		),
		presentation_variants: ['image'],
		readiness: 'planned',
		availability: 'unavailable',
		blocking_reasons: [
			...SPATIAL_BLOCKING,
			'The shared evaluator only rejects undeclared ids when the closed set is named `options`; region ids are therefore not checked against the declared regions.'
		],
		path_to_readiness: [
			...SPATIAL_PATH,
			'Teach the evaluator to validate a selected region against the declared region set.'
		],
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/ImageHotspotInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence:
				'capabilities/views.test.ts asserts absence from the generation-ready selection view'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	},
	{
		id: 'drag-label',
		native_path: 'learn',
		kind: 'interaction',
		contract_version: CONTRACT_VERSION,
		purpose: 'Have a learner attach each label to its correct target on a visual.',
		cognitive_job: 'label the parts of a representation',
		supported_intents: ['name-parts', 'show-structure', 'practise-guided'],
		supported_actions: ['place-labels'],
		choose_when:
			'Not yet. The mapping is meaningful, but no authoring path produces verified label targets for a real asset.',
		reject_when:
			'Always, for generated content: targets cannot be guessed from an unrelated image, and none can currently be authored.',
		prerequisites: [
			'An asset-region authoring model that binds an existing asset id to named label targets.',
			'A verified keyboard path to every target.'
		],
		requires: [
			'an existing asset id with alt text',
			'unique label ids',
			'every label target declared against the asset'
		],
		capacity: { labelsMin: 3, labelsMax: 8, labelMaxWords: 8 },
		payload_schema_ref: 'learn/drag-label/config.v1',
		payload_schema: CONFIG_SCHEMAS['drag-label']!,
		field_guidance: {
			pairs: '`left` is the label id, `right` is the target id it belongs to.',
			image: 'Reference an asset that already exists, with alt text describing what it carries.'
		},
		examples: [],
		negative_cases: [
			'targets estimated from an unrelated image',
			'no asset id',
			'the same label placed twice'
		],
		renderer_ref: `${SOURCE_DIR}/DragLabelInteraction.svelte`,
		response_schema: RESPONSE_SCHEMAS['drag-label']!,
		evaluation: {
			mode: 'auto-score',
			contract_ref: `${EVALUATOR}#evaluateMatchPairs`,
			partial_scoring: true,
			invalid_response_policy: 'reject'
		},
		allowed_config: {},
		default_behaviour: { max_attempts: 2 },
		asset_requirements: {
			kinds: ['image', 'svg'],
			identity: 'An existing asset id. An unresolved asset is a tracked dependency, not a blank render.',
			coordinate_system: 'named targets bound to the asset; positions not authorable today',
			authoring_tool: null
		},
		accessibility: accessibility(
			'Delegates to the match-pairs shell: a label is activated then a target, so no pointer drag is required.'
		),
		presentation_variants: ['image'],
		readiness: 'planned',
		availability: 'unavailable',
		blocking_reasons: [
			...SPATIAL_BLOCKING,
			'The renderer delegates to the match-pairs shell and never draws the asset, so the declared image is not consumed.'
		],
		path_to_readiness: [
			...SPATIAL_PATH,
			'Render the asset with positioned targets instead of delegating to the text match-pairs shell.'
		],
		readiness_evidence: {
			source_path: `${SOURCE_DIR}/DragLabelInteraction.svelte`,
			data_schema: true,
			evaluator: true,
			authoring_support: false,
			renderer: true,
			keyboard_operable: true,
			contract_export: true,
			consumer_selection_support: false,
			evidence:
				'capabilities/views.test.ts asserts absence from the generation-ready selection view'
		},
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	}
];
