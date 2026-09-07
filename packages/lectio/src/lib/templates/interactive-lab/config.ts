import type { TemplateContract } from '$lib/templates/types';

import { interactiveLabPresetIds } from './presets';

export const interactiveLabContract: TemplateContract = {
	id: 'interactive-lab',
	name: 'Interactive Lab',
	family: 'visual-exploration',
	intent: 'explain-visually',
	tagline: 'Manipulate variables, observe the result, then read why it works.',
	readingStyle: 'visual-first',
	tags: ['STEM', 'Simulation-first', 'Discovery', 'Screen-first'],
	bestFor: [
		'STEM topics where hands-on exploration reveals the concept',
		'lessons where the formula is best understood through manipulation',
		'physics, chemistry, and statistics simulations'
	],
	notIdealFor: [
		'topics that require significant context before interaction makes sense',
		'narrative or history-driven subjects with no quantitative relationships'
	],
	learnerFit: ['visual', 'general', 'scaffolded'],
	subjects: ['mathematics', 'physics', 'chemistry', 'statistics'],
	interactionLevel: 'high',
	always_present: ['section-header', 'what-next-bridge'],
	contextually_present: ['simulation-block'],
	available_components: [
		'hook-hero',
		'explanation-block',
		'definition-card',
		'worked-example-card',
		'practice-stack',
		'pitfall-alert',
		'diagram-block',
		'callout-block',
		'student-textbox',
		'summary-block',
		'short-answer',
		'section-divider'
	],
	component_budget: { 'simulation-block': 2 },
	max_per_section: { 'diagram-block': 1, 'worked-example-card': 1, 'practice-stack': 1 },
	signal_affinity: {
		topic_type: { concept: 0.5, process: 0.6, facts: 0.3, mixed: 0.6 },
		learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.7, 'remember-terms': 0.3, 'apply-to-new': 0.9 },
		class_style: { 'needs-explanation-first': 0.3, 'responds-to-worked-examples': 0.5, 'engages-with-visuals': 0.8, 'restless-without-activity': 1.0, 'tries-before-told': 1.0 },
		format: { 'printed-booklet': 0.1, 'screen-based': 1.0, both: 0.4 }
	},
	section_role_defaults: {
		intro: ['hook-hero'],
		discover: ['simulation-block', 'callout-block'],
		explain: ['explanation-block', 'definition-card'],
		practice: ['practice-stack', 'student-textbox'],
		summary: ['summary-block', 'what-next-bridge']
	},
	defaultBehaviours: {
		'practice-stack': 'hint-toggle',
		'diagram-block': 'zoom'
	},
	layoutNotes: [
		'Simulation is the hero element — it sits immediately after the hook, full width.',
		'Explanation follows the simulation, framed as confirmation of what the learner just explored.',
		'Single column layout keeps attention on the interactive.'
	],
	responsiveRules: [
		'Simulation stays full width at all breakpoints.',
		'Reduce simulation height on mobile if resizable is true.'
	],
	printRules: [
		'Replace simulation with its fallback diagram.',
		'Add a note indicating the interactive is available online.'
	],
	allowedPresets: [...interactiveLabPresetIds],
	whyThisTemplateExists:
		'Some concepts are best understood by doing first. This template puts the interactive front and centre so learners discover the pattern before reading the formal explanation.',
	generationGuidance: {
		tone: 'curious and encouraging — frame explanation as confirming what the learner just discovered',
		pacing: 'brisk setup, generous exploration, concise theory',
		chunking: 'short',
		emphasis: 'simulation context before formal definitions',
		avoid: ['leading with theory before the interactive', 'long prose before the simulation']
	},
	preview: {
		subjectExample: 'Physics',
		sectionTitle: "Newton's Second Law of Motion",
		previewContentId: 'lab-phys-01'
	}
};
