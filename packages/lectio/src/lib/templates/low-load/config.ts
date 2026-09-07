import type { TemplateContract } from '$lib/templates/types';

import { lowLoadPresetIds } from './presets';

export const lowLoadContract: TemplateContract = {
	id: 'low-load',
	name: 'Low Load',
	family: 'focus-accommodation',
	intent: 'reduce-overload',
	tagline: 'Reduce simultaneous load and present one meaningful chunk at a time.',
	readingStyle: 'chunked-focus',
	tags: ['ADHD-friendly', 'Reduced clutter', 'Single-column', 'Supportive pacing'],
	bestFor: [
		'learners who benefit from fewer competing elements',
		'ADHD-friendly and dyslexia-sensitive support',
		'scaffolded classroom or intervention settings'
	],
	notIdealFor: ['dense comparison lessons', 'topics that require multiple simultaneous visuals'],
	learnerFit: ['adhd-friendly', 'dyslexia-sensitive', 'scaffolded'],
	subjects: ['mathematics', 'science', 'english'],
	interactionLevel: 'light',
	always_present: ['section-header', 'explanation-block', 'what-next-bridge'],
	contextually_present: [],
	available_components: ['hook-hero', 'definition-card', 'callout-block', 'student-textbox', 'summary-block', 'short-answer', 'section-divider', 'key-fact', 'pitfall-alert'],
	component_budget: {},
	max_per_section: { 'quiz-check': 1, 'practice-stack': 1, 'definition-card': 1, 'callout-block': 3 },
	signal_affinity: {
		topic_type: { concept: 0.8, process: 0.7, facts: 0.8, mixed: 0.6 },
		learning_outcome: { 'understand-why': 0.7, 'be-able-to-do': 0.7, 'remember-terms': 0.8, 'apply-to-new': 0.5 },
		class_style: { 'needs-explanation-first': 1.0, 'responds-to-worked-examples': 0.7, 'engages-with-visuals': 0.5, 'restless-without-activity': 0.4, 'tries-before-told': 0.2 },
		format: { 'printed-booklet': 0.9, 'screen-based': 0.7, both: 0.8 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'callout-block'],
		explain: ['explanation-block', 'key-fact'],
		practice: ['student-textbox', 'short-answer'],
		summary: ['summary-block', 'what-next-bridge']
	},
	defaultBehaviours: {
		'practice-stack': 'flat-list',
		'glossary-inline': 'hint-toggle',
		'definition-card': 'plain-formal-toggle'
	},
	layoutNotes: [
		'Keep the page in a strict single-column flow.',
		'Use stronger spacing and fewer simultaneous elements.',
		'Vocabulary support should appear in place, not as a competing sidebar.'
	],
	responsiveRules: [
		'Maintain the same single-column rhythm on all breakpoints.',
		'Avoid introducing sidebars or split columns at larger sizes.'
	],
	printRules: [
		'Keep the same chunked order in print.',
		'Render practice in flat list order with space preserved.'
	],
	allowedPresets: [...lowLoadPresetIds],
	whyThisTemplateExists:
		'Accommodation is not only a color choice. This template structurally lowers cognitive load by removing simultaneous competition on the page.',
	generationGuidance: {
		tone: 'calm and supportive',
		pacing: 'slow enough to breathe between ideas',
		chunking: 'short',
		emphasis: 'one idea at a time',
		avoid: ['visual crowding', 'long explanatory walls', 'competing side content']
	},
	preview: {
		subjectExample: 'Mathematics',
		sectionTitle: 'Fractions as equal parts',
		previewContentId: 'math-focus-01'
	}
};
