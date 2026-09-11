import { describe, expect, it } from 'vitest';
import { clampStageIndex } from './student-shell';

describe('student shell helpers', () => {
	it('clamps stage index for compact phone nav', () => {
		expect(clampStageIndex(-1, 3)).toBe(0);
		expect(clampStageIndex(9, 3)).toBe(2);
		expect(clampStageIndex(1, 0)).toBe(0);
	});
});
