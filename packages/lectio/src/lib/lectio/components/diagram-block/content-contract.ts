import type { LectioContentContract } from '$lib/lectio/core/content-contract';
import { metadata } from './metadata';

export const contentContract = {
	componentId: metadata.id,
	sectionField: metadata.sectionField,
	fieldContracts: {
		image_url: {
			format: 'media_url',
			description: 'Raster diagram image URL.',
			renderBehavior: 'Rendered as a responsive <img> when present. Callout overlays use the same percentage coordinates as SVG paths.'
		},
		svg_content: {
			format: 'plain_text',
			description: 'Optional inline SVG document string.',
			renderBehavior: 'Sanitized SVG inserted when image_url is absent.',
			constraints: ['SVG must be safe/trusted content before sanitization.']
		},
		caption: {
			format: 'plain_text',
			description: 'Figure caption displayed under the diagram.',
			renderBehavior: 'Plain text caption line.'
		},
		alt_text: {
			format: 'accessibility_text',
			description: 'Accessibility description for screen readers.',
			renderBehavior: 'Plain descriptive text.'
		},
		zoom_label: {
			format: 'plain_text_short',
			description: 'Short label used in zoom/detail affordances.',
			renderBehavior: 'Plain text.'
		},
		figure_number: {
			format: 'number',
			description: 'Optional numeric figure identifier.',
			renderBehavior: 'Displayed as a figure chip when provided.'
		},
		callouts: {
			format: 'positioned_callouts',
			description: 'Labeled points on the diagram with percentage coordinates.',
			renderBehavior:
				'Rendered as positioned overlays on raster or SVG output. x/y are percentages from 0 to 100 relative to the diagram viewport.',
			constraints: [
				'Keep labels short.',
				'Explanations should clarify the labeled region.',
				'Compatible with image-based and SVG-based diagrams.'
			]
		},
		description: {
			format: 'block_markdown',
			description: 'Extended description of the diagram for side-by-side layout.',
			renderBehavior:
				'When present, diagram renders in a two-column grid: image left, description right.',
			constraints: [
				'Keep under 80 words.',
				'Describe what the diagram shows and why it matters.'
			]
		},
		figure_ref: {
			format: 'plain_text_short',
			description: 'Sequential figure reference label.',
			renderBehavior: 'Rendered as a label above or beside the caption.',
			constraints: [
				'Use format "Figure X.Y" where X is section number and Y is figure sequence.'
			]
		}
	},
	componentConstraints: [
		'Provide either image_url or svg_content for a visible diagram.',
		'Keep callout coordinates inside 0–100 for both raster and vector diagrams.'
	]
} satisfies LectioContentContract;
