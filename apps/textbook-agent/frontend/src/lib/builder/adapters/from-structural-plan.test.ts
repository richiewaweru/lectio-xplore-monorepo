import { describe, expect, it, vi } from 'vitest';

import { v3StructuralPlanToBuilderDocument } from './from-structural-plan';

describe('v3StructuralPlanToBuilderDocument', () => {
	it('creates a minimal document without persisted plan skeletons', () => {
		vi.stubGlobal('crypto', { randomUUID: () => 'document-1' });
		const document = v3StructuralPlanToBuilderDocument(
			{
				lesson_mode: 'first_exposure',
				lesson_intent: { goal: 'Understand fractions', structure_rationale: 'Build gradually' },
				anchor: { example: 'Pizza', reuse_scope: 'all sections' },
				sections: [
					{ id: 'intro', title: 'Meet fractions', role: 'intro', visual_required: false, transition_note: null, components: [] },
					{ id: 'practice', title: 'Try it', role: 'practice', visual_required: false, transition_note: null, components: [] }
				],
				question_plan: []
			},
			{ generationId: 'gen-1', title: 'Fraction lesson' }
		);

		expect(document.source_generation_id).toBe('gen-1');
		expect(document.sections).toEqual([]);
		expect(document.blocks).toEqual({});
	});
});
