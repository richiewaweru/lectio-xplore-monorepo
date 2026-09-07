import type { TemplatePreview } from '$lib/templates/types';

export const formalTrackPreview: TemplatePreview = {
	section: {
		section_id: 'math-formal-01',
		template_id: 'formal-track',
		header: {
			title: 'The formal derivative definition',
			subtitle: 'A rigorous limit statement for local change',
			subject: 'Mathematics',
			section_number: 'Section 08',
			grade_band: 'advanced',
			objectives: ['Interpret and apply the formal limit definition of the derivative.']
		},
		hook: {
			headline: 'How do we define local slope without hand-waving?',
			body: 'The derivative must be defined by a statement strong enough to survive proof, notation, and edge cases. The limit definition gives that precision.',
			anchor: 'precision matters because informal slope language eventually breaks'
		},
		explanation: {
			body: 'For a function f, the derivative at a is defined by the limit of the difference quotient as h approaches zero, provided that limit exists. This definition does not assume a tangent line first and justify it later. Instead, the limit statement is primary and the geometric interpretation follows from it.',
			emphasis: ['difference quotient', 'limit exists', 'geometric interpretation follows']
		},
		definition: {
			term: 'Derivative at a point',
			formal: "The derivative of f at a is f'(a) = lim_{h -> 0} (f(a+h) - f(a)) / h, when this limit exists.",
			plain: 'The local slope obtained from a limit of nearby average slopes.',
			notation: "f'(a) = \\lim_{h \\to 0} \\frac{f(a+h)-f(a)}{h}",
			symbol: "f'(a)"
		},
		worked_example: {
			title: 'Apply the definition to f(x) = x^2',
			setup: 'Evaluate the difference quotient before taking the limit.',
			steps: [
				{
					label: 'Substitute into the quotient',
					content: 'Compute ( (a+h)^2 - a^2 ) / h.'
				},
				{
					label: 'Expand and simplify',
					content: 'The numerator becomes 2ah + h^2, so the quotient simplifies to 2a + h.'
				},
				{
					label: 'Take the limit',
					content: 'As h approaches 0, 2a + h approaches 2a.'
				}
			],
			conclusion: 'Therefore the derivative of x^2 at a is 2a.',
			answer: "f'(a) = 2a"
		},
		practice: {
			problems: [
				{
					difficulty: 'medium',
					question: 'State the difference quotient for f(x) = 3x + 1 at x = a.',
					hints: [{ level: 1, text: 'Replace f(a+h) and f(a) before simplifying.' }],
					solution: {
						approach: 'Write the quotient directly from the definition.',
						answer: '(3(a+h)+1 - (3a+1)) / h'
					},
					writein_lines: 3
				},
				{
					difficulty: 'cold',
					question: 'Why does the limit definition require h to approach 0 instead of equal 0?',
					hints: [{ level: 1, text: 'Think about the denominator.' }],
					solution: {
						approach: 'Use the idea of nearby values rather than substitution.',
						answer:
							'Because h = 0 would make the denominator zero, so the definition uses nearby values and a limit.'
					},
					writein_lines: 4
				}
			]
		},
		what_next: {
			body: 'With the formal definition in place, the next step is deriving rules that let us compute derivatives efficiently.',
			next: 'Derivative rules',
			preview: 'The power rule and its companions compress repeated limit work.'
		}
	},
	summary:
		'An advanced mathematics preview that keeps the surface quiet and lets the formal definition lead.'
};
