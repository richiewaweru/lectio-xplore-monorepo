import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		title: {
			format: 'plain_text',
			description: 'Short title for the worked example.',
			renderBehavior: 'Rendered as a readable heading line.'
		},
		setup: {
			format: 'inline_markdown',
			description: 'Context framing the example.',
			renderBehavior: 'Inline markdown with optional emphasis and inline math.'
		},
		'steps[].label': {
			format: 'plain_text_short',
			description: 'Short label for each reasoning step.',
			renderBehavior: 'Displayed next to step content.'
		},
		'steps[].content': {
			format: 'block_markdown',
			description: 'Main text for the step.',
			renderBehavior: 'Block markdown with support for lists and math.'
		},
		'steps[].note': {
			format: 'inline_markdown',
			description: 'Optional side note for a step.',
			renderBehavior: 'Inline markdown.'
		},
		'steps[].formula': {
			format: 'latex_raw',
			description: 'Standalone equation material for the step.',
			constraints: ['Use raw LaTeX.', 'Do not wrap in delimiters unless the renderer applies math mode.']
		},
		conclusion: {
			format: 'inline_markdown',
			description: 'Closing takeaway tying steps together.',
			renderBehavior: 'Inline markdown.'
		},
		answer: {
			format: 'plain_text',
			description: 'Short canonical answer line when provided.',
			renderBehavior: 'Plain text result line.'
		},
		diagram: {
			format: 'structured_object',
			description: 'Optional diagram attached to the worked example.',
			renderBehavior: 'Rendered with the shared diagram surface when present.'
		}
	},
	componentConstraints: [
		'Each step should represent one clear reasoning move.',
		'Keep formulas as raw LaTeX in formula fields.'
	]
} satisfies LectioContentContract;
