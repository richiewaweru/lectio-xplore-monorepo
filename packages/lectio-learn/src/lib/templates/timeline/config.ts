import type { TemplateContract } from '$lib/templates/types';

import { timelinePresetIds } from './presets';

export const timelineContract: TemplateContract = {
	id: 'timeline',
	name: 'Timeline',
	family: 'narrative-timeline',
	intent: 'teach-sequence',
	tagline:
		'Teach through chronology so the learner experiences the concept as forward motion through time.',
	readingStyle: 'chronological',
	tags: ['Timeline', 'Narrative', 'History-ready', 'Cause and consequence'],
	bestFor: [
		'history lessons and discovery stories',
		'topics where sequence and cause matter more than static definition',
		'learners who retain ideas best as a story'
	],
	notIdealFor: [
		'pure classification lessons',
		'procedures where the learner must execute each step directly'
	],
	learnerFit: ['narrative', 'general'],
	subjects: ['history', 'science', 'english'],
	interactionLevel: 'medium',
	always_present: ['section-header', 'what-next-bridge'],
	contextually_present: ['timeline-block'],
	available_components: [
		'hook-hero',
		'explanation-block',
		'key-fact',
		'callout-block',
		'insight-strip',
		'student-textbox',
		'summary-block',
		'short-answer',
		'section-divider',
		'pitfall-alert'
	],
	component_budget: { 'timeline-block': 1 },
	max_per_section: { 'insight-strip': 1, 'quiz-check': 1 },
	signal_affinity: {
		topic_type: { concept: 0.4, process: 0.7, facts: 0.8, mixed: 0.6 },
		learning_outcome: { 'understand-why': 0.7, 'be-able-to-do': 0.3, 'remember-terms': 0.8, 'apply-to-new': 0.5 },
		class_style: { 'needs-explanation-first': 0.6, 'responds-to-worked-examples': 0.3, 'engages-with-visuals': 0.8, 'restless-without-activity': 0.5, 'tries-before-told': 0.4 },
		format: { 'printed-booklet': 0.8, 'screen-based': 0.8, both: 0.9 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'callout-block'],
		timeline: ['timeline-block', 'key-fact'],
		explain: ['explanation-block', 'insight-strip'],
		practice: ['short-answer', 'student-textbox'],
		summary: ['summary-block', 'what-next-bridge']
	},
	defaultBehaviours: {
		'timeline-block': 'timeline-scrubber',
		'practice-stack': 'accordion'
	},
	layoutNotes: [
		'The timeline is the spine of the page.',
		'Short explanation and reflection blocks help the learner make sense of the chronology.'
	],
	responsiveRules: [
		'Keep the timeline above the explanatory prose on all breakpoints.',
		'The scrubber should degrade gracefully to a readable event stack.'
	],
	printRules: [
		'Flatten the timeline into a vertical event list in print.',
		'Keep reflection and practice below the full chronology.'
	],
	allowedPresets: [...timelinePresetIds],
	whyThisTemplateExists:
		'Some knowledge is understood as a story with causes and consequences. This template lets time itself become the reading order.',
	generationGuidance: {
		tone: 'story-forward and explanatory',
		pacing: 'chronological',
		chunking: 'event by event',
		emphasis: 'show how one moment leads to the next',
		avoid: ['dropping the chronology', 'isolated facts with no sequence']
	},
	preview: {
		subjectExample: 'History',
		sectionTitle: 'How germ theory took hold',
		previewContentId: 'hist-timeline-01'
	}
};
