// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import {
	getNewAiBlockAssist,
	getStreamIntoBuilder,
	NEW_AI_BLOCK_ASSIST_KEY,
	setNewAiBlockAssist,
	setStreamIntoBuilder,
	STREAM_INTO_BUILDER_KEY
} from './flags';

describe('stream-into-builder setting', () => {
	beforeEach(() => localStorage.clear());

	it('defaults to false and persists changes', () => {
		expect(getStreamIntoBuilder()).toBe(false);
		setStreamIntoBuilder(true);
		expect(localStorage.getItem(STREAM_INTO_BUILDER_KEY)).toBe('true');
		expect(getStreamIntoBuilder()).toBe(true);
	});
});

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
