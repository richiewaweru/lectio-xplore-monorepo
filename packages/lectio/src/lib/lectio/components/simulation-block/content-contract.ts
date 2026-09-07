import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		'spec.type': {
			format: 'plain_text',
			description: 'Discriminator string for the embedded interaction.',
			renderBehavior: 'Plain text token consumed by the interaction host.'
		},
		'spec.goal': {
			format: 'plain_text',
			description: 'Human-readable learning goal for the interaction.',
			renderBehavior: 'Plain text summary line.'
		},
		'spec.anchor_content': {
			format: 'structured_object',
			description: 'Structured anchor parameters for the interaction.',
			renderBehavior: 'Arbitrary JSON object interpreted by the interaction renderer.'
		},
		'spec.context': {
			format: 'structured_object',
			description: 'Visual context for the interaction (theme, colors, learner level).',
			renderBehavior: 'Passed to the interaction shell for styling and layout.'
		},
		'spec.dimensions': {
			format: 'structured_object',
			description: 'Width/height hints for the iframe surface.',
			renderBehavior: 'Controls iframe sizing hints.'
		},
		'spec.print_translation': {
			format: 'enum',
			description: 'How the interaction degrades in print (static snapshot, hide, etc.).'
		},
		html_content: {
			format: 'plain_text',
			description: 'Optional HTML bundle for iframe embedding.',
			renderBehavior: 'Trusted HTML inserted into the sandboxed iframe host.'
		},
		fallback_diagram: {
			format: 'structured_object',
			description: 'Optional DiagramContent used when iframe content is unavailable.',
			renderBehavior: 'Rendered with DiagramBlock semantics.'
		},
		explanation: {
			format: 'inline_markdown',
			description: 'Optional instructor-facing explanation of the interaction.',
			renderBehavior: 'Inline markdown helper text.'
		}
	},
	componentConstraints: [
		'Provide either html_content or a meaningful fallback_diagram for offline contexts.',
		'Keep spec.goal aligned with what the iframe interaction practices.'
	]
} satisfies LectioContentContract;
