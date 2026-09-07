import type { TemplatePreview } from '$lib/templates/types';

export const conceptCompactPreview: TemplatePreview = {
	section: {
		section_id: 'math-compact-01',
		template_id: 'concept-compact',
		header: {
			title: 'Solving two-step equations',
			subtitle: 'Reverse the operations in a steady order',
			subject: 'Mathematics',
			section_number: 'Section 05',
			grade_band: 'secondary',
			objectives: ['Solve equations by undoing operations in reverse order.']
		},
		hook: {
			headline: 'How do you get x alone without changing the equation unfairly?',
			body: 'A two-step equation looks busy, but the logic is simple: undo what happened to x in reverse order while keeping both sides balanced.',
			anchor: 'balancing fairness while isolating the variable'
		},
		explanation: {
			body: 'To solve a two-step equation, identify what operations are acting on the variable. Then undo them in reverse order. If x was multiplied after something was added, subtract first and divide second. Each move must happen on both sides so the equation stays balanced.',
			emphasis: ['reverse order', 'both sides', 'balanced']
		},
		definition: {
			term: 'Inverse operation',
			formal: 'An operation that reverses the effect of another operation.',
			plain: 'The move that undoes what was done before.'
		},
		worked_example: {
			title: 'Solve 3x + 5 = 20',
			setup: 'Work backward from the operations acting on x.',
			steps: [
				{
					label: 'Undo addition',
					content: 'Subtract 5 from both sides to get 3x = 15.'
				},
				{
					label: 'Undo multiplication',
					content: 'Divide both sides by 3 to get x = 5.'
				}
			],
			conclusion: 'The solution is x = 5.',
			answer: 'x = 5'
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question: 'Solve x + 7 = 12.',
					hints: [{ level: 1, text: 'Undo the addition.' }],
					solution: {
						approach: 'Subtract 7 from both sides.',
						answer: 'x = 5'
					},
					writein_lines: 2
				},
				{
					difficulty: 'medium',
					question: 'Solve 4x - 3 = 13.',
					hints: [{ level: 1, text: 'Undo subtraction first, then division.' }],
					solution: {
						approach: 'Add 3 to both sides, then divide by 4.',
						answer: 'x = 4'
					},
					writein_lines: 3
				}
			]
		},
		what_next: {
			body: 'Now that two-step equations feel stable, the next step is checking solutions and handling variables on both sides.',
			next: 'Variables on both sides',
			preview: 'The same balancing idea will scale to harder equations.'
		}
	},
	summary:
		'A compact algebra lesson that keeps the guided arc while moving faster than the full baseline template.'
};
