import { describe, expect, it } from 'vitest';

import { resetV3Studio, v3Studio } from './v3-studio.svelte';

describe('v3Studio reset', () => {
	it('resets stage and clears chunked state', () => {
		v3Studio.stage = 'fill';
		v3Studio.generationId = 'gen-1';
		v3Studio.chunkedState = {
			generation_id: 'gen-1',
			stage: 'plan_ready',
			structural_plan: null,
			section_briefs: {},
			failed_sections: [],
			blueprint_id: null,
			execution_started: false,
			next_action: 'approve_or_regenerate',
			inferred_lesson_mode: null,
			lesson_mode_confidence: null
		};
		resetV3Studio();
		expect(v3Studio.stage).toBe('intent');
		expect(v3Studio.generationId).toBeNull();
		expect(v3Studio.chunkedState).toBeNull();
	});
});
