import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		title: {
			format: 'plain_text',
			description: 'Title for the multi-step diagram series.',
			renderBehavior: 'Plain text.'
		},
		'diagrams[].step_label': {
			format: 'plain_text_short',
			description: 'Label for the step position in the series.',
			renderBehavior: 'Plain text.'
		},
		'diagrams[].caption': {
			format: 'plain_text',
			description: 'Caption for the individual step diagram.',
			renderBehavior: 'Plain text.'
		},
		'diagrams[].svg_content': {
			format: 'plain_text',
			description: 'Optional SVG markup for the step.',
			renderBehavior: 'Sanitized SVG when present.'
		},
		'diagrams[].image_url': {
			format: 'media_url',
			description: 'Optional raster image for the step.',
			renderBehavior: 'Rendered when svg_content is absent.'
		}
	},
	componentConstraints: [
		'Each step should include at least one visual source (SVG or image).',
		'Keep step labels parallel in tone and length.'
	]
} satisfies LectioContentContract;
