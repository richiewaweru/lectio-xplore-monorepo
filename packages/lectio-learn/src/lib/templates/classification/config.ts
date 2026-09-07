import type { TemplateContract } from '$lib/templates/types';

import { classificationPresetIds } from './presets';

export const classificationContract: TemplateContract = {
	id: 'classification',
	name: 'Classification',
	family: 'compare-distinguish',
	intent: 'compare-ideas',
	tagline:
		'Classify three or more related ideas by keeping every distinguishing criterion visible.',
	readingStyle: 'side-by-side',
	tags: ['Classification', 'Three-way contrast', 'Analytical', 'Grid-based'],
	bestFor: [
		'three-way or four-way concept distinctions',
		'classification tasks in civics, biology, or social science',
		'lessons where learners confuse adjacent categories'
	],
	notIdealFor: ['binary contrasts that only need two concepts', 'narrative or process-driven lessons'],
	learnerFit: ['analytical', 'advanced'],
	subjects: ['civics', 'biology', 'history'],
	interactionLevel: 'light',
	always_present: ['section-header', 'what-next-bridge'],
	contextually_present: [],
	available_components: ['hook-hero', 'comparison-grid', 'explanation-block', 'definition-family', 'insight-strip', 'practice-stack', 'pitfall-alert', 'callout-block', 'student-textbox', 'summary-block', 'short-answer', 'fill-in-blank', 'section-divider'],
	component_budget: { 'comparison-grid': 1 },
	max_per_section: { 'practice-stack': 1, 'quiz-check': 1 },
	signal_affinity: {
		topic_type: { concept: 0.7, process: 0.2, facts: 0.9, mixed: 0.8 },
		learning_outcome: { 'understand-why': 0.6, 'be-able-to-do': 0.4, 'remember-terms': 0.9, 'apply-to-new': 0.8 },
		class_style: { 'needs-explanation-first': 0.6, 'responds-to-worked-examples': 0.5, 'engages-with-visuals': 0.6, 'restless-without-activity': 0.5, 'tries-before-told': 0.3 },
		format: { 'printed-booklet': 0.8, 'screen-based': 0.7, both: 0.8 }
	},
	section_role_defaults: {
		intro: ['hook-hero'],
		compare: ['comparison-grid'],
		explain: ['explanation-block', 'definition-family'],
		practice: ['practice-stack', 'fill-in-blank'],
		summary: ['summary-block', 'what-next-bridge']
	},
	defaultBehaviours: {
		'practice-stack': 'flat-list'
	},
	layoutNotes: [
		'The grid holds three or more categories in view simultaneously.',
		'Short framing text should clarify the classification criteria before practice.'
	],
	responsiveRules: [
		'Allow the grid to scroll horizontally on smaller screens.',
		'Keep the apply practice in a single block beneath the grid.'
	],
	printRules: [
		'Print as a wide classification table.',
		'Use flat practice so the learner can write directly below the contrast.'
	],
	allowedPresets: [...classificationPresetIds],
	whyThisTemplateExists:
		'Two-way contrasts are not always enough. This template helps learners classify among several neighboring categories without losing the criteria.',
	generationGuidance: {
		tone: 'precise and classificatory',
		pacing: 'frame the criteria before applying them',
		chunking: 'tight',
		emphasis: 'help the learner sort categories confidently',
		avoid: ['unlabeled criteria', 'classification practice without a visible grid']
	},
	preview: {
		subjectExample: 'Civics',
		sectionTitle: 'Unitary, federal, and confederal systems',
		previewContentId: 'civics-distinction-01'
	}
};
