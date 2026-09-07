import type { TemplatePreview } from '$lib/templates/types';

export const procedurePreview: TemplatePreview = {
	section: {
		section_id: 'chem-process-01',
		template_id: 'procedure',
		header: {
			title: 'Balancing chemical equations',
			subtitle: 'Use a repeatable order instead of guessing coefficients',
			subject: 'Chemistry',
			section_number: 'Section 10',
			grade_band: 'secondary',
			objectives:
				['Balance simple chemical equations by adjusting coefficients in a stable order.']
		},
		hook: {
			headline:
				'How do you make both sides show the same atoms without changing the substances?',
			body: 'Balancing equations works when you follow a repeatable method. If you guess, you usually lose track of which atom changed where.',
			anchor: 'the learner needs a reliable sequence instead of trial and error'
		},
		explanation: {
			body: 'Balancing an equation means making the atom count match on both sides without changing any chemical formulas. Coefficients are the tool because they scale whole substances. A good procedure starts with elements that appear in fewer places and checks totals at the end.',
			emphasis: ['coefficients', 'do not change formulas', 'check totals']
		},
		process: {
			title: 'Balance in this order',
			intro: 'Use the same routine each time to avoid chasing your own changes.',
			steps: [
				{
					number: 1,
					action: 'Count atoms first',
					detail:
						'List how many atoms of each element appear on both sides before changing anything.'
				},
				{
					number: 2,
					action: 'Adjust one substance with coefficients',
					detail:
						'Change coefficients, not subscripts, so the substance identity stays the same.'
				},
				{
					number: 3,
					action: 'Recount and repeat',
					detail:
						'After each change, recount all affected elements before moving on.'
				},
				{
					number: 4,
					action: 'Verify every element',
					detail:
						'Finish by checking that each element matches on both sides.'
				}
			]
		},
		worked_example: {
			title: 'Balance H2 + O2 -> H2O',
			setup: 'Follow the procedure without changing the formulas.',
			steps: [
				{
					label: 'Count first',
					content:
						'Hydrogen starts at 2 on the left and 2 on the right, but oxygen is 2 on the left and 1 on the right.'
				},
				{
					label: 'Fix oxygen',
					content: 'Put a 2 in front of H2O so oxygen becomes 2 on the right.'
				},
				{
					label: 'Recount hydrogen',
					content: 'Now hydrogen is 4 on the right, so put a 2 in front of H2 on the left.'
				}
			],
			conclusion: 'The balanced equation is 2H2 + O2 -> 2H2O.',
			answer: '2H2 + O2 -> 2H2O'
		},
		pitfall: {
			misconception:
				'You can balance an equation by changing the small numbers in the formulas',
			correction:
				'Changing subscripts changes the substance itself. Only coefficients are allowed when balancing.',
			example: 'Turning H2O into H2O2 would describe a different substance.'
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question: 'Balance N2 + H2 -> NH3.',
					hints: [{ level: 1, text: 'Match nitrogen first, then recount hydrogen.' }],
					solution: {
						approach: 'Use coefficients and recount after each change.',
						answer: 'N2 + 3H2 -> 2NH3'
					},
					writein_lines: 3
				},
				{
					difficulty: 'medium',
					question: 'Why is changing a subscript not allowed when balancing an equation?',
					hints: [{ level: 1, text: 'Ask what the subscript says about the substance.' }],
					solution: {
						approach: 'Connect subscripts to substance identity.',
						answer:
							'Because it changes which substance is present instead of just changing how many units there are.'
					},
					writein_lines: 4
				}
			]
		},
		what_next: {
			body: 'With the procedure stable, the next step is balancing larger equations with polyatomic ions and multiple products.',
			next: 'More complex equations',
			preview: 'The same routine scales up once the basic discipline is secure.'
		}
	},
	summary:
		'A chemistry procedure lesson that makes the balancing routine explicit and rehearsable.'
};
