import { describe, expect, it } from 'vitest';

import { parseIncomingSection } from './parse-section';

const validSection = {
	section_id: 's-01',
	template_id: 'guided-concept-path',
	header: {
		title: 'Why limits matter',
		subject: 'Calculus',
		grade_band: 'secondary'
	},
	hook: {
		headline: 'What happens right before we arrive?',
		body: 'Limits help us describe approach without needing the final value yet.',
		anchor: 'limits'
	},
	explanation: {
		body: 'A limit studies nearby behavior.',
		emphasis: ['nearby behavior']
	},
	practice: {
		problems: [
			{
				difficulty: 'warm',
				question: 'Describe what happens near x = 2.',
				hints: [{ level: 1, text: 'Look close to 2.' }]
			},
			{
				difficulty: 'medium',
				question: 'Estimate the limit of x^2 near 2.',
				hints: [{ level: 1, text: 'Square numbers near 2.' }]
			}
		]
	},
	what_next: {
		body: 'Next we connect limits to continuity.',
		next: 'Continuity'
	}
};

describe('parseIncomingSection', () => {
	it('accepts a valid section payload', () => {
		expect(parseIncomingSection(validSection)).toMatchObject({
			section_id: 's-01',
			template_id: 'guided-concept-path'
		});
	});

	it('throws a precise error for invalid section payloads', () => {
		expect(() =>
			parseIncomingSection({
				...validSection,
				what_next: {
					body: 'Next we connect limits to continuity.'
				}
			})
		).toThrow(/Invalid section from pipeline/);
	});
});
