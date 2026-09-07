import { calculusSection } from '$lib/dev/dummy-content';
import type { TemplatePreview } from '$lib/templates/types';

export const guidedConceptPathPreview: TemplatePreview = {
	section: {
		...calculusSection,
		template_id: 'guided-concept-path'
	},
	summary:
		'A first-exposure calculus section that shows the full scaffold from hook to worked example to practice.'
};
