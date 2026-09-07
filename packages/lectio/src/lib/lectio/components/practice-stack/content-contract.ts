import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		'problems[].question': {
			format: 'block_markdown',
			description: 'The problem statement shown to the learner.',
			renderBehavior: 'Rendered as block markdown.'
		},
		'problems[].hints[].text': {
			format: 'block_markdown',
			description: 'Progressive hint text for a given hint level.',
			renderBehavior: 'Rendered as block markdown inside the hint stack.'
		},
		'problems[].hints[].level': {
			format: 'enum',
			description: 'Hint level (1, 2, or 3).',
			constraints: ['Levels should increase in strength.', 'Use 1 (light), 2 (medium), or 3 (strong).']
		},
		'problems[].solution.approach': {
			format: 'block_markdown',
			description: 'High-level solution approach when a solution is provided.',
			renderBehavior: 'Rendered as block markdown.'
		},
		'problems[].solution.answer': {
			format: 'block_markdown',
			description: 'Final answer text.',
			renderBehavior: 'Rendered as block markdown.'
		},
		'problems[].solution.worked': {
			format: 'block_markdown',
			description: 'Optional extended worked explanation.',
			renderBehavior: 'Rendered as block markdown.'
		},
		'problems[].diagram': {
			format: 'structured_object',
			description: 'Optional instructional diagram payload matching DiagramContent.',
			renderBehavior: 'Rendered using the shared diagram renderer when present.'
		},
		'problems[].difficulty': {
			format: 'enum',
			description: 'Declared difficulty band for the problem.'
		}
	},
	componentConstraints: [
		'Order hints from light support to stronger support.',
		'Problem difficulty must use the supported enum values.'
	]
} satisfies LectioContentContract;
