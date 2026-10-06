import { describe, expect, it } from 'vitest';
import { savePrediction } from './local-eval';

describe('prediction evaluation', () => {
	it('uses the existing ungraded outcome and no score fields', () => {
		expect(savePrediction({ correct: 'right', incorrect: 'wrong', saved: 'Saved.' })).toEqual({
			outcome: 'pending-review',
			feedback: 'Saved.'
		});
	});
});
