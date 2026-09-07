import type { TemplateContract } from '$lib/templates/types';

import { procedurePresetIds } from './presets';

export const procedureContract: TemplateContract = {
	id: 'procedure',
	name: 'Procedure',
	family: 'process-procedure',
	intent: 'teach-procedure',
	tagline: 'Turn a repeatable procedure into a clear sequence the learner can follow and rehearse.',
	readingStyle: 'process-led',
	tags: ['Procedure', 'Stepwise', 'Worked case', 'Print-friendly'],
	bestFor: [
		'repeatable methods in math and science',
		'algorithmic or checklist-driven tasks',
		'lessons where order is non-negotiable'
	],
	notIdealFor: [
		'open-ended narrative topics',
		'classification lessons with no clear execution order'
	],
	learnerFit: ['general', 'scaffolded'],
	subjects: ['mathematics', 'chemistry', 'physics'],
	interactionLevel: 'light',
	always_present: ['section-header', 'what-next-bridge'],
	contextually_present: ['process-steps'],
	available_components: [
		'hook-hero',
		'explanation-block',
		'worked-example-card',
		'practice-stack',
		'pitfall-alert',
		'callout-block',
		'student-textbox',
		'summary-block',
		'short-answer',
		'fill-in-blank',
		'section-divider',
		'key-fact'
	],
	component_budget: {},
	max_per_section: { 'worked-example-card': 1, 'practice-stack': 1, 'quiz-check': 1 },
	signal_affinity: {
		topic_type: { concept: 0.3, process: 1.0, facts: 0.4, mixed: 0.5 },
		learning_outcome: { 'understand-why': 0.4, 'be-able-to-do': 1.0, 'remember-terms': 0.5, 'apply-to-new': 0.7 },
		class_style: { 'needs-explanation-first': 0.5, 'responds-to-worked-examples': 0.9, 'engages-with-visuals': 0.4, 'restless-without-activity': 0.7, 'tries-before-told': 0.5 },
		format: { 'printed-booklet': 0.9, 'screen-based': 0.7, both: 0.8 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'callout-block'],
		process: ['process-steps', 'key-fact'],
		explain: ['worked-example-card', 'explanation-block'],
		practice: ['practice-stack', 'student-textbox'],
		summary: ['summary-block', 'what-next-bridge']
	},
	defaultBehaviours: {
		'process-steps': 'step-reveal',
		'practice-stack': 'flat-list'
	},
	layoutNotes: [
		'The process steps are the backbone of the page.',
		'A worked case appears after the steps to show the procedure in action.'
	],
	responsiveRules: [
		'Keep the procedure visible above the worked case on all breakpoints.',
		'Use a single-column flow so the learner can follow with one finger.'
	],
	printRules: [
		'Expand the full process sequence in print.',
		'Keep practice directly below the method.'
	],
	allowedPresets: [...procedurePresetIds],
	whyThisTemplateExists:
		'Some lessons are primarily about doing the method correctly. This template makes the procedure unmistakable and rehearsable.',
	generationGuidance: {
		tone: 'clear and procedural',
		pacing: 'ordered and steady',
		chunking: 'step by step',
		emphasis: 'show why each step enables the next',
		avoid: ['jumping ahead', 'burying the method under too much exposition']
	},
	preview: {
		subjectExample: 'Chemistry',
		sectionTitle: 'Balancing chemical equations',
		previewContentId: 'chem-process-01'
	}
};
