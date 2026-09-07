import type { TemplateContract } from '$lib/templates/types';

import { visualLedPresetIds } from './presets';

export const visualLedContract: TemplateContract = {
	id: 'visual-led',
	name: 'Visual Led',
	family: 'visual-exploration',
	intent: 'explain-visually',
	tagline: 'Let a single dominant figure do the teaching before prose names what it shows.',
	readingStyle: 'visual-first',
	tags: ['Visual-first', 'Diagram zoom', 'Science-ready', 'Screen-first'],
	bestFor: [
		'biology, chemistry, geography, and anatomy lessons',
		'topics where the learner needs a spatial anchor before vocabulary lands',
		'visual or mixed-modality classrooms'
	],
	notIdealFor: ['topics with little visual structure', 'proof-style or text-dense formal lessons'],
	learnerFit: ['visual', 'general'],
	subjects: ['biology', 'chemistry', 'geography', 'science'],
	interactionLevel: 'medium',
	always_present: [
		'section-header',
		'what-next-bridge'
	],
	contextually_present: [],
	available_components: [
		'hook-hero',
		'diagram-block',
		'diagram-compare',
		'diagram-series',
		'explanation-block',
		'definition-card',
		'practice-stack',
		'callout-block',
		'student-textbox',
		'summary-block',
		'key-fact',
		'short-answer',
		'section-divider'
	],
	component_budget: { 'diagram-block': 3, 'diagram-compare': 1, 'diagram-series': 1 },
	max_per_section: { 'practice-stack': 1 },
	defaultBehaviours: {
		'diagram-block': 'zoom',
		'practice-stack': 'accordion',
		'glossary-rail': 'inline-strip',
		'process-steps': 'step-reveal'
	},
	signal_affinity: {
		topic_type: { concept: 0.7, process: 0.6, facts: 0.5, mixed: 0.7 },
		learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.4, 'remember-terms': 0.5, 'apply-to-new': 0.6 },
		class_style: { 'needs-explanation-first': 0.4, 'responds-to-worked-examples': 0.4, 'engages-with-visuals': 1.0, 'restless-without-activity': 0.5, 'tries-before-told': 0.5 },
		format: { 'printed-booklet': 0.6, 'screen-based': 0.9, both: 0.7 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'diagram-block'],
		explain: ['diagram-block', 'explanation-block'],
		visual: ['diagram-block', 'callout-block'],
		practice: ['practice-stack', 'student-textbox'],
		summary: ['summary-block', 'what-next-bridge']
	},
	layoutNotes: [
		'The figure is the main teaching surface high on the page.',
		'Supporting prose and process notes clarify the figure instead of replacing it.',
		'Vocabulary support stays in-line rather than in a sidebar.'
	],
	responsiveRules: [
		'Keep the figure near the top on all breakpoints.',
		'Stack explanation and process support beneath the figure on smaller screens.'
	],
	printRules: [
		'Render the diagram as a full-width static figure in print.',
		'Expand process steps in print so no interaction is required.'
	],
	allowedPresets: [...visualLedPresetIds],
	whyThisTemplateExists:
		'Some ideas become understandable the moment the learner can point at the structure. This template lets the figure do that work first.',
	generationGuidance: {
		tone: 'observational and clear',
		pacing: 'front-load the visual anchor',
		chunking: 'medium',
		emphasis: 'name what the learner can already see',
		avoid: [
			'burying the figure below the fold',
			'text that repeats the caption without adding meaning'
		]
	},
	preview: {
		subjectExample: 'Biology',
		sectionTitle: 'How photosynthesis moves energy',
		previewContentId: 'bio-figure-first-01'
	}
};
