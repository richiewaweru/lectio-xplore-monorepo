/**
 * Package-derived Builder editors for Learn interaction configs (P06).
 * Schemas mirror CONFIG_SCHEMAS / capability field_guidance — not hand-drawn forms.
 */

import type { EditSchema, FieldSchema } from './edit-schemas';
import { CONFIG_SCHEMAS } from '../learn/capabilities/schemas';
import { LEARN_INTERACTION_COMPONENT_PREFIX } from './document';

const PROMPT_FIELD: FieldSchema = {
	field: 'prompt',
	label: 'Prompt',
	input: 'textarea',
	required: true,
	help: 'Shown above the interaction control.'
};

const ASSESSMENT_FIELD: FieldSchema = {
	field: 'assessment_mode',
	label: 'Assessment mode',
	input: 'select',
	required: true,
	options: [
		{ value: 'practice', label: 'Practice' },
		{ value: 'graded', label: 'Graded' }
	]
};

const FEEDBACK_FIELDS: FieldSchema[] = [
	{
		field: 'feedback.correct',
		label: 'Feedback (correct)',
		input: 'textarea',
		required: false
	},
	{
		field: 'feedback.incorrect',
		label: 'Feedback (incorrect)',
		input: 'textarea',
		required: false
	},
	{
		field: 'feedback.partial',
		label: 'Feedback (partial)',
		input: 'textarea',
		required: false
	}
];

function choiceEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}choice`,
		fields: [
			PROMPT_FIELD,
			ASSESSMENT_FIELD,
			{
				field: 'options',
				label: 'Options',
				input: 'object-list',
				required: true,
				maxItems: 5,
				itemSchema: [
					{ field: 'id', label: 'Option id', input: 'text', required: true },
					{ field: 'text', label: 'Text', input: 'text', required: true, maxWords: 20 },
					{ field: 'explanation', label: 'Distractor note', input: 'text', required: false }
				]
			},
			{
				field: 'correct_option_id',
				label: 'Correct option id',
				input: 'text',
				required: true,
				help: 'Must equal exactly one option id.'
			},
			...FEEDBACK_FIELDS
		]
	};
}

function multiSelectEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}multi-select`,
		fields: [
			PROMPT_FIELD,
			ASSESSMENT_FIELD,
			{
				field: 'options',
				label: 'Options',
				input: 'object-list',
				required: true,
				maxItems: 6,
				itemSchema: [
					{ field: 'id', label: 'Option id', input: 'text', required: true },
					{ field: 'text', label: 'Text', input: 'text', required: true }
				]
			},
			{
				field: 'correct_option_ids',
				label: 'Correct option ids',
				input: 'list',
				required: true,
				help: 'Every id must name a declared option.'
			},
			...FEEDBACK_FIELDS
		]
	};
}

function fillBlankEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}fill-blank`,
		fields: [
			PROMPT_FIELD,
			ASSESSMENT_FIELD,
			{
				field: 'answers',
				label: 'Accepted answers (per blank)',
				input: 'list',
				required: true,
				help: 'One entry per blank. Alternatives for a blank can be comma-separated.'
			},
			{
				field: 'blank_ids',
				label: 'Blank ids',
				input: 'list',
				required: false
			},
			...FEEDBACK_FIELDS
		]
	};
}

function numericEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}numeric`,
		fields: [
			PROMPT_FIELD,
			ASSESSMENT_FIELD,
			{
				field: 'value',
				label: 'Accepted value',
				input: 'text',
				required: true
			},
			{
				field: 'tolerance',
				label: 'Tolerance',
				input: 'text',
				required: false
			},
			{
				field: 'unit',
				label: 'Unit',
				input: 'text',
				required: false
			},
			...FEEDBACK_FIELDS
		]
	};
}

function shortResponseEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}short-response`,
		fields: [
			PROMPT_FIELD,
			ASSESSMENT_FIELD,
			{
				field: 'evaluation',
				label: 'Evaluation mode',
				input: 'select',
				required: true,
				options: [
					{ value: 'accepted-answers', label: 'Accepted answers' },
					{ value: 'teacher-review', label: 'Teacher review' }
				]
			},
			{
				field: 'accepted_answers',
				label: 'Accepted answers',
				input: 'list',
				required: false,
				help: 'Required when evaluation is accepted-answers.'
			},
			{
				field: 'review_guidance',
				label: 'Review guidance',
				input: 'textarea',
				required: false
			},
			...FEEDBACK_FIELDS
		]
	};
}

function matchPairsEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}match-pairs`,
		fields: [
			PROMPT_FIELD,
			ASSESSMENT_FIELD,
			{
				field: 'pairs',
				label: 'Pairs',
				input: 'object-list',
				required: true,
				itemSchema: [
					{ field: 'left', label: 'Left', input: 'text', required: true },
					{ field: 'right', label: 'Right', input: 'text', required: true }
				]
			},
			...FEEDBACK_FIELDS
		]
	};
}

function classifyEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}classify`,
		fields: [
			PROMPT_FIELD,
			ASSESSMENT_FIELD,
			{
				field: 'pairs',
				label: 'Item → category',
				input: 'object-list',
				required: true,
				itemSchema: [
					{ field: 'left', label: 'Item', input: 'text', required: true },
					{ field: 'right', label: 'Category', input: 'text', required: true }
				],
				help: 'Each item belongs to exactly one category.'
			},
			{
				field: 'categories',
				label: 'Categories',
				input: 'object-list',
				required: false,
				itemSchema: [
					{ field: 'id', label: 'Category id', input: 'text', required: true },
					{ field: 'label', label: 'Label', input: 'text', required: true }
				]
			},
			...FEEDBACK_FIELDS
		]
	};
}

function sequenceEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}sequence`,
		fields: [
			{
				...PROMPT_FIELD,
				placeholder: 'Ask the learner to put the stages in order',
				help: 'Shown above the ordering control.'
			},
			ASSESSMENT_FIELD,
			{
				field: 'order',
				label: 'Accepted order (item ids)',
				input: 'list',
				required: true,
				help: 'Exactly one accepted order. Ids must match the items below.',
				maxItems: 7
			},
			{
				field: 'items',
				label: 'Items',
				input: 'object-list',
				required: true,
				maxItems: 7,
				itemSchema: [
					{ field: 'id', label: 'Item id', input: 'text', required: true },
					{ field: 'label', label: 'Label', input: 'text', required: true, maxWords: 12 }
				],
				help: 'Labels shown to the learner, keyed by the same ids used in order.'
			},
			...FEEDBACK_FIELDS
		]
	};
}

const INTERACTION_EDIT_SCHEMAS: Record<string, EditSchema> = {
	choice: choiceEditSchema(),
	'multi-select': multiSelectEditSchema(),
	'fill-blank': fillBlankEditSchema(),
	numeric: numericEditSchema(),
	'short-response': shortResponseEditSchema(),
	'match-pairs': matchPairsEditSchema(),
	classify: classifyEditSchema(),
	sequence: sequenceEditSchema()
};

/** True when CONFIG_SCHEMAS declares a closed payload for this kind. */
export function hasInteractionConfigSchema(kind: string): boolean {
	return Boolean(CONFIG_SCHEMAS[kind as keyof typeof CONFIG_SCHEMAS]);
}

export function getInteractionEditSchema(kindOrComponentId: string): EditSchema | null {
	const kind = kindOrComponentId.startsWith(LEARN_INTERACTION_COMPONENT_PREFIX)
		? kindOrComponentId.slice(LEARN_INTERACTION_COMPONENT_PREFIX.length)
		: kindOrComponentId;
	return INTERACTION_EDIT_SCHEMAS[kind] ?? null;
}

/**
 * Flatten a LearnInteractionContract into a Builder field bag for BlockEditor.
 */
export function interactionContractToEditorContent(
	contract: Record<string, unknown>
): Record<string, unknown> {
	const config = (contract.config as Record<string, unknown> | undefined) ?? {};
	const feedback = (contract.feedback as Record<string, unknown> | undefined) ?? {};
	return {
		prompt: contract.prompt,
		assessment_mode: contract.assessment_mode ?? 'practice',
		order: Array.isArray(config.order) ? [...config.order] : [],
		items: Array.isArray(config.items) ? structuredClone(config.items) : [],
		options: Array.isArray(config.options) ? structuredClone(config.options) : [],
		correct_option_id: config.correct_option_id ?? '',
		correct_option_ids: Array.isArray(config.correct_option_ids)
			? [...config.correct_option_ids]
			: [],
		answers: Array.isArray(config.answers) ? structuredClone(config.answers) : [],
		blank_ids: Array.isArray(config.blank_ids) ? [...config.blank_ids] : [],
		value: config.value ?? '',
		tolerance: config.tolerance ?? '',
		unit: config.unit ?? '',
		evaluation: config.evaluation ?? 'accepted-answers',
		accepted_answers: Array.isArray(config.accepted_answers)
			? [...config.accepted_answers]
			: [],
		review_guidance: config.review_guidance ?? '',
		pairs: Array.isArray(config.pairs) ? structuredClone(config.pairs) : [],
		categories: Array.isArray(config.categories) ? structuredClone(config.categories) : [],
		'feedback.correct': feedback.correct ?? '',
		'feedback.incorrect': feedback.incorrect ?? '',
		'feedback.partial': feedback.partial ?? ''
	};
}

/**
 * Apply a Builder field edit onto a LearnInteractionContract (immutable).
 */
export function applyInteractionEditorField(
	contract: Record<string, unknown>,
	field: string,
	value: unknown
): Record<string, unknown> {
	const next = structuredClone(contract) as Record<string, unknown>;
	const config = {
		...((next.config as Record<string, unknown> | undefined) ?? {})
	};
	const feedback = {
		...((next.feedback as Record<string, unknown> | undefined) ?? {})
	};

	if (field === 'prompt') {
		next.prompt = value;
	} else if (field === 'assessment_mode') {
		next.assessment_mode = value;
	} else if (field.startsWith('feedback.')) {
		feedback[field.slice('feedback.'.length)] = value;
	} else if (
		[
			'order',
			'items',
			'options',
			'correct_option_id',
			'correct_option_ids',
			'answers',
			'blank_ids',
			'value',
			'tolerance',
			'unit',
			'evaluation',
			'accepted_answers',
			'review_guidance',
			'pairs',
			'categories'
		].includes(field)
	) {
		config[field] = value;
	} else {
		(next as Record<string, unknown>)[field] = value;
	}

	next.config = config;
	next.feedback = feedback;
	return next;
}

export function interactionEditFields(): FieldSchema[] {
	return sequenceEditSchema().fields;
}
