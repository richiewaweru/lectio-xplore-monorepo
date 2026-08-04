// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import {
	getNewAiBlockAssist,
	NEW_AI_BLOCK_ASSIST_KEY,
	setNewAiBlockAssist
} from './flags';

describe('new AI block assistance setting', () => {
	beforeEach(() => localStorage.clear());

	it('defaults to enabled and preserves explicit choices', () => {
		expect(getNewAiBlockAssist()).toBe(true);
		setNewAiBlockAssist(false);
		expect(localStorage.getItem(NEW_AI_BLOCK_ASSIST_KEY)).toBe('false');
		expect(getNewAiBlockAssist()).toBe(false);
		setNewAiBlockAssist(true);
		expect(getNewAiBlockAssist()).toBe(true);
	});
});
