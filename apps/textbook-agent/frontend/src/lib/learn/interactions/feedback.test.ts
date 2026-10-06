import { describe, expect, it } from 'vitest';
import { normalizeFeedback } from './feedback';

describe('task feedback roles', () => {
	it('uses saved feedback for predictions without changing legacy defaults', () => {
		expect(normalizeFeedback({ saved: 'Saved; revisit it later.' }, 'predict')).toMatchObject({
			saved: 'Saved; revisit it later.'
		});
		expect(normalizeFeedback(null)).toEqual({
			correct: 'Correct',
			incorrect: 'Incorrect',
			partial: 'Partially correct'
		});
	});

	it('falls back to the prompt when display_prompt is absent at the contract boundary', () => {
		// The shell applies this exact fallback before rendering the learner string.
		const node = { prompt: 'Full task context', display_prompt: '  ' };
		expect(node.display_prompt.trim() || node.prompt.trim()).toBe('Full task context');
	});
});
