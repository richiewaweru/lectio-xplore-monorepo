import type { TemplateContract } from '$lib/templates/types';

import { guidedDiscoveryPresetIds } from './presets';

export const guidedDiscoveryContract: TemplateContract = {
	id: 'guided-discovery',
	name: 'Guided Discovery',
	family: 'guided-concept',
	intent: 'introduce-concept',
	tagline: 'Read the concept, then test it hands-on before practising.',
	readingStyle: 'linear-guided',
	tags: ['Scaffolded', 'Simulation-supported', 'Glossary sidebar', 'Screen-first'],
	bestFor: [
		'concepts that need context before interaction makes sense',
		'lessons where learners benefit from explanation then verification',
		'STEM and life-science topics with quantitative relationships'
	],
	notIdealFor: [
		'topics best learned through pure exploration without guidance',
		'highly visual subjects where the figure should lead entirely'
	],
	learnerFit: ['general', 'scaffolded', 'analytical'],
	subjects: ['mathematics', 'physics', 'biology', 'chemistry'],
	interactionLevel: 'high',
	always_present: ['section-header', 'hook-hero', 'explanation-block', 'what-next-bridge'],
	contextually_present: [],
	available_components: [
		'simulation-block',
		'definition-card',
		'worked-example-card',
		'practice-stack',
		'pitfall-alert',
		'glossary-rail',
		'diagram-block',
		'reflection-prompt',
		'callout-block',
		'student-textbox',
		'summary-block',
		'short-answer',
		'section-divider'
	],
	component_budget: { 'simulation-block': 2 },
	max_per_section: { 'diagram-block': 1, 'worked-example-card': 1, 'practice-stack': 1, 'reflection-prompt': 1 },
	signal_affinity: {
		topic_type: { concept: 0.7, process: 0.5, facts: 0.4, mixed: 0.7 },
		learning_outcome: { 'understand-why': 0.9, 'be-able-to-do': 0.7, 'remember-terms': 0.4, 'apply-to-new': 0.8 },
		class_style: { 'needs-explanation-first': 0.8, 'responds-to-worked-examples': 0.6, 'engages-with-visuals': 0.7, 'restless-without-activity': 0.7, 'tries-before-told': 0.6 },
		format: { 'printed-booklet': 0.3, 'screen-based': 1.0, both: 0.5 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'callout-block'],
		explain: ['explanation-block', 'definition-card'],
		discover: ['simulation-block', 'callout-block'],
		practice: ['practice-stack', 'student-textbox'],
		summary: ['summary-block', 'reflection-prompt', 'what-next-bridge']
	},
	defaultBehaviours: {
		'practice-stack': 'progressive-hints',
		'glossary-rail': 'sticky',
		'worked-example-card': 'step-reveal',
		'diagram-block': 'zoom'
	},
	layoutNotes: [
		'Two-column layout: main content with glossary sidebar on desktop.',
		'Simulation appears after explanation — learners verify what they just read.',
		'Reflection prompt closes the loop before the what-next bridge.'
	],
	responsiveRules: [
		'Collapse glossary sidebar into inline vocabulary below tablet.',
		'Simulation stays full width of the main column at all breakpoints.'
	],
	printRules: [
		'Replace simulation with its fallback diagram.',
		'Flatten glossary rail into inline notes at section end.',
		'Expand step-reveal worked examples for print.'
	],
	allowedPresets: [...guidedDiscoveryPresetIds],
	whyThisTemplateExists:
		'Not every concept is best learned by jumping in blind. This template gives learners enough context to interact meaningfully, then uses the simulation to confirm and deepen understanding.',
	generationGuidance: {
		tone: 'clear and teacherly — build understanding before interaction',
		pacing: 'steady, explanation-first',
		chunking: 'medium',
		emphasis: 'explanation leads, simulation confirms',
		avoid: ['skipping explanation before simulation', 'overwhelming the interactive with too much context']
	},
	preview: {
		subjectExample: 'Mathematics',
		sectionTitle: 'Probability of Compound Events',
		previewContentId: 'disc-math-01'
	}
};
