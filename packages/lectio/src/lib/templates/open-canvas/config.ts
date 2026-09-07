import type { TemplateContract } from '$lib/templates/types';

import { openCanvasPresetIds } from './presets';

export const openCanvasContract: TemplateContract = {
	id: 'open-canvas',
	name: 'Open Canvas',
	family: 'guided-concept',
	intent: 'introduce-concept',
	tagline: 'Full component vocabulary. No fixed structure. Compose freely.',
	readingStyle: 'linear-guided',
	tags: ['Custom', 'Flexible', 'All subjects', 'Teacher-directed'],

	bestFor: [
		'lessons that do not fit any standard template pattern',
		'experienced teachers who want full control over structure',
		'revision sheets, mixed-format lessons, or unusual combinations'
	],
	notIdealFor: [
		'first-time users — start with a structured template',
		'lessons where a defined pedagogical arc is important'
	],

	learnerFit: ['general', 'advanced', 'scaffolded', 'visual', 'analytical'],
	subjects: [
		'mathematics', 'science', 'history', 'english', 'economics',
		'biology', 'chemistry', 'physics', 'geography', 'civics'
	],
	interactionLevel: 'medium',

	always_present: [],
	contextually_present: [],

	available_components: [
		'hook-hero',
		'explanation-block',
		'prerequisite-strip',
		'interview-anchor',
		'callout-block',
		'summary-block',
		'section-divider',
		'definition-card',
		'definition-family',
		'glossary-rail',
		'insight-strip',
		'key-fact',
		'worked-example-card',
		'comparison-grid',
		'process-steps',
		'practice-stack',
		'quiz-check',
		'reflection-prompt',
		'student-textbox',
		'short-answer',
		'fill-in-blank',
		'pitfall-alert',
		'diagram-block',
		'diagram-compare',
		'diagram-series',
		'timeline-block',
		'simulation-block'
	],

	component_budget: {
		'simulation-block': 2,
		'diagram-compare': 2,
		'diagram-series': 2,
		'comparison-grid': 2,
		'timeline-block': 2
	},

	max_per_section: {},

	defaultBehaviours: {},

	signal_affinity: {
		topic_type: {
			concept: 0.5, process: 0.5, facts: 0.5, mixed: 0.5
		},
		learning_outcome: {
			'understand-why': 0.5, 'be-able-to-do': 0.5,
			'remember-terms': 0.5, 'apply-to-new': 0.5
		},
		class_style: {
			'tries-before-told': 0.5, 'needs-explanation-first': 0.5,
			'engages-with-visuals': 0.5, 'responds-to-worked-examples': 0.5,
			'restless-without-activity': 0.5
		},
		format: { 'printed-booklet': 0.5, 'screen-based': 0.5, both: 0.5 }
	},

	section_role_defaults: {
		intro: ['hook-hero', 'callout-block'],
		explain: ['explanation-block'],
		practice: ['practice-stack', 'student-textbox'],
		summary: ['summary-block', 'what-next-bridge']
	},

	layoutNotes: [
		'Single column. Render components in plan order.',
		'No sidebar. No fixed structure.'
	],
	responsiveRules: ['Single column at all breakpoints.'],
	printRules: ['Expand all collapsible content. Render write-in lines for student inputs.'],

	allowedPresets: [...openCanvasPresetIds],

	whyThisTemplateExists:
		'No set of fixed templates covers every lesson. Open Canvas ensures the system never forces a bad fit and gives experienced teachers a structured way to compose freely.',

	generationGuidance: {
		tone: "match the teacher's stated intent and audience",
		pacing: 'determined by the section plan, not a fixed arc',
		chunking: 'follow the component sequence in the plan',
		emphasis: 'fill each component well — do not invent structure beyond what the plan selected',
		avoid: [
			'adding components not in the section plan',
			'imposing a pedagogical arc that was not planned'
		]
	},

	preview: {
		subjectExample: 'Mixed',
		sectionTitle: 'Open structure example',
		previewContentId: 'open-canvas-01'
	}
};
