import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		before_svg: {
			format: 'plain_text',
			description: 'Optional SVG markup for the before panel.',
			renderBehavior: 'Sanitized SVG string.'
		},
		after_svg: {
			format: 'plain_text',
			description: 'Optional SVG markup for the after panel.',
			renderBehavior: 'Sanitized SVG string.'
		},
		before_image_url: {
			format: 'media_url',
			description: 'Optional raster image URL for the before panel.',
			renderBehavior: 'Rendered as <img> when provided.'
		},
		after_image_url: {
			format: 'media_url',
			description: 'Optional raster image URL for the after panel.',
			renderBehavior: 'Rendered as <img> when provided.'
		},
		before_label: {
			format: 'plain_text',
			description: 'Short label for the before column.',
			renderBehavior: 'Plain text.'
		},
		after_label: {
			format: 'plain_text',
			description: 'Short label for the after column.',
			renderBehavior: 'Plain text.'
		},
		before_details: {
			format: 'structured_array',
			description: 'Optional bullet strings elaborating the before state.',
			renderBehavior: 'Plain text entries.'
		},
		after_details: {
			format: 'structured_array',
			description: 'Optional bullet strings elaborating the after state.',
			renderBehavior: 'Plain text entries.'
		},
		caption: {
			format: 'plain_text',
			description: 'Shared caption for the compare figure.',
			renderBehavior: 'Plain text.'
		},
		alt_text: {
			format: 'accessibility_text',
			description: 'Accessibility description covering both panels.',
			renderBehavior: 'Plain text.'
		}
	},
	componentConstraints: [
		'Provide either SVG or image URLs for each side you want to show.',
		'Keep column labels short; they appear in compact headers.'
	]
} satisfies LectioContentContract;
