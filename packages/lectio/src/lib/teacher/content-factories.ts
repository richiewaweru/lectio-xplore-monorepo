import { getComponentFieldMap } from '../schema/registry';
import type { GradeBand } from '../schema/types';

const defaultGrade: GradeBand = 'secondary';

const factories: Record<string, () => Record<string, unknown>> = {
	'section-header': () => ({
		title: '',
		subject: '',
		grade_band: defaultGrade,
		objectives: []
	}),
	'hook-hero': () => ({
		headline: '',
		body: '',
		anchor: '',
		type: 'prose' as const
	}),
	'explanation-block': () => ({
		body: '',
		emphasis: []
	}),
	'prerequisite-strip': () => ({
		items: [] as { concept: string; refresher?: string }[]
	}),
	'what-next-bridge': () => ({
		body: '',
		next: ''
	}),
	'interview-anchor': () => ({
		prompt: '',
		audience: ''
	}),
	'callout-block': () => ({
		variant: 'info' as const,
		body: ''
	}),
	'summary-block': () => ({
		items: [] as { text: string }[]
	}),
	'section-divider': () => ({
		label: ''
	}),
	'definition-card': () => ({
		term: '',
		formal: '',
		plain: ''
	}),
	'definition-family': () => ({
		family_title: '',
		family_intro: '',
		definitions: [{ term: '', formal: '', plain: '' }]
	}),
	'glossary-rail': () => ({
		terms: [] as { term: string; definition: string }[]
	}),
	'insight-strip': () => ({
		cells: [
			{ label: '', value: '' },
			{ label: '', value: '' }
		]
	}),
	'key-fact': () => ({
		fact: ''
	}),
	'comparison-grid': () => ({
		title: '',
		intro: '',
		columns: [
			{ id: 'col-1', title: 'Option A', summary: '' },
			{ id: 'col-2', title: 'Option B', summary: '' }
		],
		rows: [{ criterion: '', values: [{ text: '' }, { text: '' }], takeaway: '' }],
		apply_prompt: ''
	}),
	'worked-example-card': () => ({
		title: '',
		setup: '',
		steps: [] as { label: string; content: string }[],
		conclusion: ''
	}),
	'process-steps': () => ({
		title: '',
		steps: [] as { number: number; action: string; detail: string }[]
	}),
	'practice-stack': () => ({
		problems: [
			{
				difficulty: 'warm' as const,
				question: '',
				hints: [] as { level: 1 | 2 | 3; text: string }[]
			},
			{
				difficulty: 'medium' as const,
				question: '',
				hints: []
			}
		]
	}),
	'quiz-check': () => ({
		question: '',
		options: [
			{ text: '', correct: false, explanation: '' },
			{ text: '', correct: false, explanation: '' },
			{ text: '', correct: true, explanation: '' }
		],
		feedback_correct: '',
		feedback_incorrect: ''
	}),
	'answer-key': () => ({
		label: 'Answer key',
		entries: [] as {
			question_number: number;
			question: string;
			correct_answer: string;
		}[]
	}),
	'reflection-prompt': () => ({
		prompt: '',
		type: 'open' as const
	}),
	'student-textbox': () => ({
		prompt: ''
	}),
	'short-answer': () => ({
		question: ''
	}),
	'fill-in-blank': () => ({
		instruction: 'Fill in each blank with the correct word.',
		segments: [
			{ text: 'The answer is ', is_blank: false },
			{ text: '', is_blank: true, answer: '' }
		] as { text: string; is_blank: boolean; answer?: string }[],
		word_bank: [] as { word: string }[]
	}),
	'pitfall-alert': () => ({
		misconception: '',
		correction: ''
	}),
	'diagram-block': () => ({
		media_id: '',
		image_url: '',
		svg_content: '',
		caption: '',
		alt_text: '',
		width: 'full' as const
	}),
	'diagram-compare': () => ({
		before_media_id: '',
		after_media_id: '',
		before_svg: '',
		after_svg: '',
		before_image_url: '',
		after_image_url: '',
		before_label: '',
		after_label: '',
		caption: '',
		alt_text: ''
	}),
	'diagram-series': () => ({
		title: '',
		diagrams: [
			{
				media_id: '',
				image_url: '',
				svg_content: '',
				step_label: '',
				caption: ''
			}
		]
	}),
	'video-embed': () => ({
		media_id: '',
		print_fallback: 'thumbnail' as const
	}),
	'image-block': () => ({
		media_id: '',
		alt_text: '',
		width: 'full' as const,
		alignment: 'center' as const
	}),
	'timeline-block': () => ({
		title: '',
		events: [] as { id: string; year: string; title: string; summary: string }[]
	}),
	'simulation-block': () => ({
		spec: {
			type: 'graph_slider' as const,
			goal: '',
			anchor_content: {},
			context: {
				learner_level: '',
				template_id: '',
				color_mode: 'light' as const,
				accent_color: '',
				surface_color: '',
				font_mono: ''
			},
			dimensions: { width: '100%', height: 400, resizable: false },
			print_translation: 'static_midstate' as const
		}
	})
};

/**
 * Valid placeholder content for a component. Required fields use empty or minimal values.
 */
export function getEmptyContent(componentId: string): Record<string, unknown> {
	const factory = factories[componentId];
	if (!factory) {
		throw new Error(`[Lectio] No empty content factory for component "${componentId}"`);
	}
	return factory();
}

/**
 * Richer demo content for palette previews. Extend per-component as needed.
 */
export function getPreviewContent(componentId: string): Record<string, unknown> | null {
	return getEmptyContent(componentId);
}

/** Every component with a section field must have a factory (builder + document conversion). */
export function assertFactoriesCoverRegistry(): void {
	const map = getComponentFieldMap();
	for (const componentId of Object.keys(map)) {
		if (!factories[componentId]) {
			throw new Error(`[Lectio] Missing getEmptyContent factory for "${componentId}"`);
		}
	}
}
