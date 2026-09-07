import type { TemplateContract } from '$lib/templates/types';

import { conceptCompactPresetIds } from './presets';

export const conceptCompactContract: TemplateContract = {
	id: 'concept-compact',
	name: 'Concept Compact',
	family: 'guided-concept',
	intent: 'introduce-concept',
	tagline:
		'Keep the same guided arc, but compress it for confident learners and tighter lessons.',
	readingStyle: 'linear-guided',
	tags: ['Compact', 'Single-column', 'Fast pace', 'Light interaction'],
	bestFor: [
		'confident learners who still benefit from a clear arc',
		'shorter classroom segments',
		'revision lessons that still need a quick concept scaffold'
	],
	notIdealFor: [
		'learners who need heavy vocabulary or side support',
		'topics that require a dominant figure or comparison spine'
	],
	learnerFit: ['general', 'advanced'],
	subjects: ['mathematics', 'science', 'economics', 'english'],
	interactionLevel: 'light',
	always_present: [
		'section-header',
		'hook-hero',
		'explanation-block',
		'what-next-bridge'
	],
	contextually_present: [],
	available_components: [
		'definition-card',
		'worked-example-card',
		'practice-stack',
		'pitfall-alert',
		'callout-block',
		'student-textbox',
		'summary-block',
		'short-answer',
		'section-divider'
	],
	component_budget: {},
	max_per_section: { 'worked-example-card': 1, 'practice-stack': 1, 'quiz-check': 1 },
	defaultBehaviours: {
		'worked-example-card': 'accordion',
		'practice-stack': 'accordion'
	},
	signal_affinity: {
		topic_type: { concept: 0.9, process: 0.5, facts: 0.7, mixed: 0.6 },
		learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.5, 'remember-terms': 0.7, 'apply-to-new': 0.5 },
		class_style: { 'needs-explanation-first': 0.9, 'responds-to-worked-examples': 0.7, 'engages-with-visuals': 0.3, 'restless-without-activity': 0.3, 'tries-before-told': 0.3 },
		format: { 'printed-booklet': 0.8, 'screen-based': 0.7, both: 0.8 }
	},
	section_role_defaults: {
		intro: ['hook-hero'],
		explain: ['explanation-block', 'definition-card'],
		practice: ['practice-stack'],
		summary: ['summary-block', 'what-next-bridge']
	},
	layoutNotes: [
		'Stay in a single column with no sidebar.',
		'Use a shorter concept arc than Guided Concept Path.'
	],
	responsiveRules: ['Keep the same single-column pacing at all sizes.'],
	printRules: ['Expand accordion content in print.', 'Keep the order compact and uninterrupted.'],
	allowedPresets: [...conceptCompactPresetIds],
	whyThisTemplateExists:
		'Not every guided lesson needs the full side support. This version keeps the pedagogy but trims the surface area.',
	generationGuidance: {
		tone: 'direct and efficient',
		pacing: 'faster than the full guided path',
		chunking: 'tight',
		emphasis: 'clarity without extra support furniture',
		avoid: ['too many optional blocks', 'slow detours']
	},
	preview: {
		subjectExample: 'Mathematics',
		sectionTitle: 'Solving two-step equations',
		previewContentId: 'math-compact-01'
	}
};
