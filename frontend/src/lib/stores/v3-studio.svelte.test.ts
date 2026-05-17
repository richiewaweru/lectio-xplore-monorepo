import { describe, expect, it } from 'vitest';

import { resetV3Studio, v3Studio } from './v3-studio.svelte';

describe('v3Studio architect mode', () => {
	it('defaults to standard and resets back to standard', () => {
		expect(v3Studio.architectMode).toBe('standard');

		v3Studio.architectMode = 'chunked';
		expect(v3Studio.architectMode).toBe('chunked');

		resetV3Studio();
		expect(v3Studio.architectMode).toBe('standard');
	});
});
