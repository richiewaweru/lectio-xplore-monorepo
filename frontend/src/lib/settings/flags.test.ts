// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest';

import {
	getStreamIntoBuilder,
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
