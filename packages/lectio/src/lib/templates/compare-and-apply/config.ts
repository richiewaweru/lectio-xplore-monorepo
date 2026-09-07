import type { TemplateContract } from '$lib/templates/types';

import { compareAndApplyPresetIds } from './presets';

export const compareAndApplyContract: TemplateContract = {
	id: 'compare-and-apply',
	name: 'Compare and Apply',
	family: 'compare-distinguish',
	intent: 'compare-ideas',
	tagline:
		'Teach the distinction by holding two ideas in view at the same time and then applying it.',
	readingStyle: 'side-by-side',
	tags: ['Comparison', 'Analytical', 'Two-column thinking', 'Apply after contrast'],
	bestFor: [
		'chemistry contrasts, biology comparisons, and civics distinctions',
		'analytical learners who benefit from explicit criteria',
		'lessons where choosing correctly depends on noticing a difference'
	],
	notIdealFor: [
		'chronological stories',
		'single-concept introductions with no meaningful rival idea'
	],
	learnerFit: ['analytical', 'general'],
	subjects: ['chemistry', 'biology', 'civics', 'literature'],
	interactionLevel: 'light',
	always_present: ['section-header', 'what-next-bridge'],
	contextually_present: [],
	available_components: ['hook-hero', 'comparison-grid', 'explanation-block', 'definition-family', 'insight-strip', 'practice-stack', 'pitfall-alert', 'callout-block', 'student-textbox', 'summary-block', 'short-answer', 'fill-in-blank', 'section-divider'],
	component_budget: { 'comparison-grid': 1 },
	max_per_section: { 'practice-stack': 1, 'quiz-check': 1 },
	signal_affinity: {
		topic_type: { concept: 0.8, process: 0.3, facts: 0.7, mixed: 0.9 },
		learning_outcome: { 'understand-why': 0.8, 'be-able-to-do': 0.5, 'remember-terms': 0.7, 'apply-to-new': 0.9 },
		class_style: { 'needs-explanation-first': 0.7, 'responds-to-worked-examples': 0.6, 'engages-with-visuals': 0.5, 'restless-without-activity': 0.5, 'tries-before-told': 0.4 },
		format: { 'printed-booklet': 0.7, 'screen-based': 0.7, both: 0.8 }
	},
	section_role_defaults: {
		intro: ['hook-hero', 'callout-block'],
		compare: ['comparison-grid', 'definition-family'],
		explain: ['explanation-block', 'insight-strip'],
		practice: ['practice-stack', 'short-answer'],
		summary: ['summary-block', 'what-next-bridge']
	},
	defaultBehaviours: {
		'practice-stack': 'accordion',
		'definition-card': 'plain-formal-toggle'
	},
	layoutNotes: [
		'The comparison grid is the center of gravity.',
		'Short framing content should clarify the contrast before practice asks the learner to choose.'
	],
	responsiveRules: [
		'The grid can scroll horizontally on smaller screens but should stay readable.',
		'Practice stays beneath the comparison rather than splitting into a sidebar.'
	],
	printRules: [
		'Render the comparison as a static table in print.',
		'Keep the apply practice directly after the contrast.'
	],
	allowedPresets: [...compareAndApplyPresetIds],
	whyThisTemplateExists:
		'Some concepts only become clear when the learner can compare them criterion by criterion. This template makes that contrast structural.',
	generationGuidance: {
		tone: 'precise and analytical',
		pacing: 'compare early, apply immediately after',
		chunking: 'tight',
		emphasis: 'surface the decision points between the ideas',
		avoid: ['burying the contrast in prose', 'practice that does not depend on the distinction']
	},
	preview: {
		subjectExample: 'Chemistry',
		sectionTitle: 'Alkanes vs alkenes',
		previewContentId: 'chem-compare-01'
	}
};
