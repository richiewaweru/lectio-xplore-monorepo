import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		'terms[].term': {
			format: 'plain_text',
			description: 'Glossary entry term.',
			renderBehavior: 'Plain text.'
		},
		'terms[].definition': {
			format: 'inline_markdown',
			description: 'Definition body for the term.',
			renderBehavior: 'Inline markdown.'
		},
		'terms[].used_in': {
			format: 'plain_text',
			description: 'Optional note about where the word appears in the lesson.',
			renderBehavior: 'Plain text.'
		},
		'terms[].pronunciation': {
			format: 'plain_text',
			description: 'Optional pronunciation hint.',
			renderBehavior: 'Plain text.'
		},
		'terms[].related': {
			format: 'structured_array',
			description: 'Optional related term strings.',
			renderBehavior: 'Plain text cross-links.'
		}
	},
	componentConstraints: ['Keep definitions short and classroom-ready for the rail layout.']
} satisfies LectioContentContract;
