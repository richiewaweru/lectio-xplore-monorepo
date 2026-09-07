import type { TemplateContract } from '$lib/templates/types';
import { CONTENT_CONTRACT_COMPONENT_IDS } from '$lib/lectio/export-policy';

import { guidedConceptPathPresetIds } from './presets';

export const guidedConceptPathContract: TemplateContract = {
	id: 'guided-concept-path',
	name: 'Guided Concept Path',
	family: 'guided-concept',
	intent: 'introduce-concept',
	tagline: 'Lead with felt need, then move steadily toward formal understanding and practice.',
	readingStyle: 'linear-guided',
	tags: ['Universal', 'Sidebar glossary', 'Step reveal', 'Screen-first'],
	bestFor: [
		'first exposure to a concept',
		'math, science, economics, and grammar lessons',
		'teacher-led or student-led structured reading'
	],
	notIdealFor: [
		'highly visual topics that need the figure to lead',
		'comparison-heavy lessons with multiple equal concepts'
	],
	learnerFit: ['general', 'scaffolded'],
	subjects: ['mathematics', 'science', 'economics', 'english'],
	interactionLevel: 'medium',
	always_present: [],
	contextually_present: [],
	available_components: [...CONTENT_CONTRACT_COMPONENT_IDS],
	component_budget: {
		'diagram-block': 3,
		'diagram-series': 2,
		'simulation-block': 1
	},
	max_per_section: { 'practice-stack': 1, 'quiz-check': 1, 'reflection-prompt': 1 },
	defaultBehaviours: {
		'worked-example-card': 'step-reveal',
		'practice-stack': 'accordion',
		'glossary-rail': 'sticky',
		'diagram-block': 'zoom'
	},
	signal_affinity: {
		topic_type: { concept: 0.9, process: 0.5, facts: 0.6, mixed: 0.7 },
		learning_outcome: { 'understand-why': 0.9, 'be-able-to-do': 0.5, 'remember-terms': 0.6, 'apply-to-new': 0.6 },
		class_style: { 'needs-explanation-first': 0.9, 'responds-to-worked-examples': 0.8, 'engages-with-visuals': 0.5, 'restless-without-activity': 0.4, 'tries-before-told': 0.3 },
		format: { 'printed-booklet': 0.7, 'screen-based': 0.8, both: 0.7 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'callout-block'],
		explain: ['explanation-block', 'definition-card', 'worked-example-card'],
		practice: ['practice-stack', 'student-textbox'],
		summary: ['summary-block', 'what-next-bridge']
	},
	layoutNotes: [
		'Main reading column leads the page.',
		'Glossary can live in a sticky right rail on desktop.',
		'Examples and practice arrive after the core explanation.'
	],
	responsiveRules: [
		'Collapse to a single reading column below desktop.',
		'Move glossary support into inline vocabulary support on smaller screens.'
	],
	printRules: [
		'Expand step-based content for print.',
		'Flatten the glossary rail into inline vocabulary notes at the end of the section.'
	],
	allowedPresets: [...guidedConceptPathPresetIds],
	whyThisTemplateExists:
		'This is the stable baseline Lectio lesson: predictable enough for first exposure, flexible enough to fit most classroom subjects.',
	generationGuidance: {
		tone: 'clear and teacherly',
		pacing: 'steady',
		chunking: 'medium',
		emphasis: 'explanation before formality',
		avoid: ['long uninterrupted prose', 'overloaded side content']
	},
	preview: {
		subjectExample: 'Mathematics',
		sectionTitle: 'Why does calculus exist?',
		previewContentId: 'calc-01'
	}
};
