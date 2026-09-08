/**
 * Package-derived Builder editors for Learn interaction configs (P06).
 * Schemas mirror CONFIG_SCHEMAS / capability field_guidance — not hand-drawn forms.
 */

import type { EditSchema, FieldSchema } from './edit-schemas';
import { CONFIG_SCHEMAS } from '../learn/capabilities/schemas';
import { LEARN_INTERACTION_COMPONENT_PREFIX } from './document';

function sequenceEditSchema(): EditSchema {
	return {
		component_id: `${LEARN_INTERACTION_COMPONENT_PREFIX}sequence`,
		fields: [
			{
				field: 'prompt',
				label: 'Prompt',
				input: 'textarea',
				required: true,
				placeholder: 'Ask the learner to put the stages in order',
				help: 'Shown above the ordering control.'
			},
			{
				field: 'assessment_mode',
				label: 'Assessment mode',
				input: 'select',
				required: true,
				options: [
					{ value: 'practice', label: 'Practice' },
					{ value: 'graded', label: 'Graded' }
				]
			},
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
		]
	};
}

const INTERACTION_EDIT_SCHEMAS: Record<string, EditSchema> = {
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
	} else if (field === 'order') {
		config.order = value;
	} else if (field === 'items') {
		config.items = value;
	} else if (field === 'feedback.correct') {
		feedback.correct = value;
	} else if (field === 'feedback.incorrect') {
		feedback.incorrect = value;
	} else if (field === 'feedback.partial') {
		feedback.partial = value;
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
