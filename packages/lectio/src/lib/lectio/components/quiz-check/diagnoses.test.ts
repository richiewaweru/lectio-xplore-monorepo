import { describe, expect, it } from 'vitest';

import { componentSchema } from './schema';

const quiz = {
	question: 'Where did most of the tree mass come from?',
	options: [
		{
			text: 'Carbon dioxide from the air',
			correct: true,
			explanation: 'Carbon is incorporated into glucose.'
		},
		{
			text: 'Minerals from the soil',
			correct: false,
			explanation: 'Minerals contribute only a small fraction of the mass.',
			diagnoses: 'M1'
		},
		{
			text: 'Energy from sunlight',
			correct: false,
			explanation: 'Light supplies energy rather than matter.',
			diagnoses: 'M2'
		}
	],
	feedback_correct: 'Correct.',
	feedback_incorrect: 'Review the source of the carbon.'
};

describe('quiz diagnoses contract', () => {
	it('accepts caller-supplied misconception ids without requiring them', () => {
		const result = componentSchema.parse(quiz);

		expect(result.options[0].diagnoses).toBeUndefined();
		expect(result.options[1].diagnoses).toBe('M1');
	});
});
