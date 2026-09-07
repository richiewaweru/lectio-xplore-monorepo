import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		family_title: {
			format: 'plain_text',
			description: 'Title for the definition cluster.',
			renderBehavior: 'Plain text.'
		},
		family_intro: {
			format: 'inline_markdown',
			description: 'Optional introduction before accordion items.',
			renderBehavior: 'Inline markdown.'
		},
		definitions: {
			format: 'structured_array',
			description: 'List of DefinitionCard-shaped objects.',
			renderBehavior: 'Each entry uses the same field semantics as definition-card.'
		}
	},
	componentConstraints: ['Keep related definitions grouped by a single conceptual family.']
} satisfies LectioContentContract;
