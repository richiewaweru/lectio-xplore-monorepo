import type { TemplateContract } from '$lib/templates/types';

import { diagramLedPresetIds } from './presets';

export const diagramLedContract: TemplateContract = {
	id: 'diagram-led',
	name: 'Diagram Led',
	family: 'visual-exploration',
	intent: 'explain-visually',
	tagline: 'Use a sequence of diagrams to teach change over stages before prose fills the gaps.',
	readingStyle: 'visual-first',
	tags: ['Diagram series', 'Stage-by-stage', 'Science-ready', 'Medium interaction'],
	bestFor: [
		'processes that unfold in visible stages',
		'science lessons where each stage changes the structure',
		'classes that benefit from stepwise visual progression'
	],
	notIdealFor: ['single static visuals', 'topics with no meaningful stage progression'],
	learnerFit: ['visual', 'general'],
	subjects: ['biology', 'chemistry', 'earth-science'],
	interactionLevel: 'medium',
	always_present: ['section-header', 'what-next-bridge'],
	contextually_present: ['diagram-block'],
	available_components: ['hook-hero', 'explanation-block', 'definition-card', 'diagram-series', 'diagram-compare', 'worked-example-card', 'practice-stack', 'pitfall-alert', 'callout-block', 'student-textbox', 'summary-block', 'key-fact', 'short-answer', 'section-divider'],
	component_budget: { 'diagram-block': 4, 'diagram-series': 1, 'diagram-compare': 1 },
	max_per_section: { 'worked-example-card': 1, 'practice-stack': 1 },
	signal_affinity: {
		topic_type: { concept: 0.8, process: 0.7, facts: 0.4, mixed: 0.7 },
		learning_outcome: { 'understand-why': 0.9, 'be-able-to-do': 0.5, 'remember-terms': 0.4, 'apply-to-new': 0.6 },
		class_style: { 'needs-explanation-first': 0.5, 'responds-to-worked-examples': 0.5, 'engages-with-visuals': 1.0, 'restless-without-activity': 0.6, 'tries-before-told': 0.5 },
		format: { 'printed-booklet': 0.7, 'screen-based': 0.9, both: 0.8 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'diagram-block'],
		explain: ['diagram-block', 'explanation-block', 'definition-card'],
		visual: ['diagram-series', 'callout-block'],
		practice: ['practice-stack', 'student-textbox'],
		summary: ['summary-block', 'what-next-bridge']
	},
	defaultBehaviours: {
		'diagram-series': 'static',
		'process-steps': 'step-reveal',
		'glossary-rail': 'inline-strip'
	},
	layoutNotes: [
		'A staged visual progression is the main structure.',
		'Prose should clarify the progression instead of replacing it.'
	],
	responsiveRules: [
		'Keep the full stage sequence above the explanatory prose.',
		'Inline glossary support remains beneath the diagrams on smaller screens.'
	],
	printRules: [
		'Print all diagrams in sequence with their stage captions.',
		'Expand the process steps below the sequence.'
	],
	allowedPresets: [...diagramLedPresetIds],
	whyThisTemplateExists:
		'Some ideas are best learned as a visible sequence. This template turns that sequence into the lesson backbone.',
	generationGuidance: {
		tone: 'observational and explanatory',
		pacing: 'move stage by stage',
		chunking: 'medium',
		emphasis: 'show how each stage changes the system',
		avoid: ['burying the stage sequence under prose', 'using only one diagram when change is the point']
	},
	preview: {
		subjectExample: 'Biology',
		sectionTitle: 'Stages of mitosis',
		previewContentId: 'bio-diagram-led-01'
	}
};
