import type { TemplateContract } from '$lib/templates/types';

import { formalTrackPresetIds } from './presets';

export const formalTrackContract: TemplateContract = {
	id: 'formal-track',
	name: 'Formal Track',
	family: 'guided-concept',
	intent: 'build-rigor',
	tagline: 'Move quickly into formal definitions and rigorous reasoning with minimal hand-holding.',
	readingStyle: 'formal-rigorous',
	tags: ['Print-first', 'Formal', 'Advanced', 'Low ornament'],
	bestFor: [
		'advanced learners',
		'proof-adjacent or definition-heavy lessons',
		'print-first or exam-prep contexts'
	],
	notIdealFor: [
		'first exposure with fragile conceptual footing',
		'learners who need heavy visual or vocabulary scaffolding'
	],
	learnerFit: ['advanced', 'analytical'],
	subjects: ['mathematics', 'physics', 'economics'],
	interactionLevel: 'none',
	always_present: [
		'section-header',
		'explanation-block',
		'what-next-bridge'
	],
	contextually_present: [],
	available_components: [
		'hook-hero',
		'definition-card',
		'worked-example-card',
		'practice-stack',
		'pitfall-alert',
		'key-fact',
		'short-answer',
		'fill-in-blank',
		'callout-block',
		'section-divider'
	],
	component_budget: {},
	max_per_section: { 'worked-example-card': 1, 'practice-stack': 1, 'quiz-check': 1 },
	defaultBehaviours: {},
	signal_affinity: {
		topic_type: { concept: 0.7, process: 0.6, facts: 0.8, mixed: 0.5 },
		learning_outcome: { 'understand-why': 0.7, 'be-able-to-do': 0.6, 'remember-terms': 0.8, 'apply-to-new': 0.7 },
		class_style: { 'needs-explanation-first': 1.0, 'responds-to-worked-examples': 0.8, 'engages-with-visuals': 0.2, 'restless-without-activity': 0.1, 'tries-before-told': 0.2 },
		format: { 'printed-booklet': 0.9, 'screen-based': 0.6, both: 0.7 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'definition-card'],
		explain: ['explanation-block', 'key-fact', 'worked-example-card'],
		practice: ['practice-stack', 'short-answer'],
		summary: ['summary-block', 'what-next-bridge']
	},
	layoutNotes: [
		'Keep the lesson in a print-first single column.',
		'Prefer formal explanation and static worked examples over progressive disclosure.'
	],
	responsiveRules: [
		'No sidebar or split layouts.',
		'Preserve the same ordering and density across breakpoints.'
	],
	printRules: [
		'Render as a clean static worksheet-like page.',
		'Avoid introducing any interaction-dependent supports.'
	],
	allowedPresets: [...formalTrackPresetIds],
	whyThisTemplateExists:
		'Some classes want the rigorous version immediately. Formal Track provides a direct path without decorative scaffolding.',
	generationGuidance: {
		tone: 'formal and precise',
		pacing: 'brisk',
		chunking: 'tight',
		emphasis: 'definitions, notation, and justification',
		avoid: ['chatty analogies', 'excess side support', 'visual ornament']
	},
	preview: {
		subjectExample: 'Mathematics',
		sectionTitle: 'The formal derivative definition',
		previewContentId: 'math-formal-01'
	}
};
