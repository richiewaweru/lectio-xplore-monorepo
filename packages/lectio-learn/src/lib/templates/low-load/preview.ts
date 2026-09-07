import type { TemplatePreview } from '$lib/templates/types';

export const lowLoadPreview: TemplatePreview = {
	section: {
		section_id: 'math-focus-01',
		template_id: 'low-load',
		header: {
			title: 'Fractions as equal parts',
			subtitle: 'Keep the attention on one idea at a time',
			subject: 'Mathematics',
			section_number: 'Section 02',
			grade_band: 'primary',
			objectives: ['Understand a fraction as equal parts of one whole.']
		},
		hook: {
			headline: 'If two slices are different sizes, can they still be halves?',
			body: 'A fraction only makes sense when the whole is split into equal parts. That one idea removes most of the confusion learners have at the start.',
			anchor: 'equal parts matter more than just counting pieces'
		},
		explanation: {
			body: 'A fraction names how many equal parts of one whole we are talking about. The denominator tells how many equal parts the whole is split into. The numerator tells how many of those equal parts we are focusing on. If the parts are not equal, the fraction name does not match the picture.',
			emphasis: ['equal parts', 'denominator', 'numerator'],
			callouts: [
				{
					type: 'remember',
					text: 'Count equal pieces, not just any pieces.'
				}
			]
		},
		definition: {
			term: 'Fraction',
			formal: 'A number that represents one or more equal parts of a whole.',
			plain: 'A way to name equal pieces of one whole.'
		},
		glossary: {
			terms: [
				{
					term: 'Denominator',
					definition: 'How many equal parts the whole is split into.'
				},
				{
					term: 'Numerator',
					definition: 'How many equal parts we are talking about.'
				}
			]
		},
		pitfall: {
			misconception: 'Any two pieces can be called halves',
			correction:
				'Halves must be equal in size because the whole has to be split into equal parts.',
			example: 'Two uneven slices do not make a half-and-half picture.'
		},
		practice: {
			problems: [
				{
					difficulty: 'warm',
					question: 'A circle is split into 4 equal pieces. What fraction is 1 piece?',
					hints: [
						{ level: 1, text: 'The denominator is the total number of equal parts.' }
					],
					solution: {
						approach:
							'Use 1 for the selected part and 4 for the equal parts in the whole.',
						answer: '1/4'
					},
					writein_lines: 2
				},
				{
					difficulty: 'medium',
					question:
						'A rectangle is split into 3 pieces, but one piece is larger than the others. Can you call one piece 1/3 of the whole?',
					hints: [{ level: 1, text: 'Ask whether the parts are equal first.' }],
					solution: {
						approach: 'Check equality before naming the fraction.',
						answer: 'No, because thirds must be equal parts.'
					},
					writein_lines: 3
				}
			]
		},
		reflection: {
			prompt: 'What is the first thing you should check before naming a fraction from a picture?',
			type: 'sentence-stem',
			sentence_stem: 'Before I name a fraction, I check...',
			space: 3
		},
		what_next: {
			body: 'Now that equal parts are secure, the next step is placing fractions on number lines.',
			next: 'Fractions on a number line',
			preview: 'The same idea of equal parts will move from shapes to distance.'
		}
	},
	summary:
		'A low-clutter fractions lesson that keeps the content in one calm column with flat practice.'
};
