import type { TemplatePreview } from '$lib/templates/types';

export const openCanvasPreview: TemplatePreview = {
	section: {
		section_id: 'open-canvas-01',
		template_id: 'open-canvas',

		header: {
			title: 'Open Canvas Demo',
			subtitle: 'A flexible lesson with no fixed structure',
			subject: 'Mixed',
			grade_band: 'secondary',
			objectives: ['Demonstrate how Open Canvas assembles diverse components freely']
		},

		hook: {
			headline: 'What if you could build any lesson you wanted?',
			body: 'Open Canvas gives you every component in the library. You choose what goes where.',
			anchor: 'Teachers want creative freedom without losing structure.'
		},

		explanation: {
			body: 'Open Canvas is the fallback template when no structured pattern fits. It includes the full component vocabulary with liberal budgets, so the planning layer can compose freely.',
			emphasis: ['full component vocabulary', 'compose freely'],
			callouts: [
				{
					type: 'insight',
					text: 'Use Open Canvas for revision sheets, mixed-format lessons, or when you want full control.'
				}
			]
		},

		practice: {
			problems: [
				{
					difficulty: 'warm',
					question: 'Name two situations where Open Canvas is a better fit than a structured template.',
					hints: [{ level: 1, text: 'Think about lessons that mix many different activity types.' }],
					solution: {
						approach: 'Consider revision sheets and teacher-directed mixed lessons.',
						answer: 'Revision sheets and unusual lesson combinations.'
					}
				},
				{
					difficulty: 'medium',
					question: 'Why does Open Canvas use uniform 0.5 signal affinity scores?',
					hints: [{ level: 1, text: 'Think about how template scoring works.' }],
					solution: {
						approach: 'Uniform scores mean it never wins against a well-matched specific template.',
						answer: 'So it only gets selected as a fallback when no specific template fits well.'
					}
				}
			]
		},

		what_next: {
			body: 'Explore the structured templates to see if one fits your next lesson better.',
			next: 'Template Gallery'
		}
	},
	summary: 'Open Canvas — full vocabulary, no fixed structure, compose freely.'
};
