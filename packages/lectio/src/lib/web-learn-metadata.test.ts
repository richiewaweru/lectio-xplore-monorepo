import { describe, it, expect } from 'vitest';
import { componentRegistry } from '$lib/schema/registry';

/**
 * Phase 02: Learn public API must not require print metadata.
 * Web hints are optional and additive.
 */

describe('@lectio/learn public metadata (web-native)', () => {
	it('does not require printFallback on registry components', () => {
		for (const [key, meta] of Object.entries(componentRegistry)) {
			// printFallback may still exist as transitional data, but must not be required.
			expect(meta.id, `${key} missing id`).toBeTruthy();
			expect(meta.teachingIntent, `${key} missing teachingIntent`).toBeTruthy();
			expect(meta.sectionField !== undefined, `${key} missing sectionField`).toBe(true);
		}
	});

	it('interactive practice components declare web interaction hints', () => {
		const expected: Record<string, string> = {
			'quiz-check': 'choice',
			'practice-stack': 'input',
			'fill-in-blank': 'input',
			'simulation-block': 'manipulation'
		};
		for (const [id, interaction] of Object.entries(expected)) {
			const meta = Object.values(componentRegistry).find((c) => c.id === id);
			expect(meta, `Component ${id} missing`).toBeDefined();
			expect(meta?.web?.interaction).toBe(interaction);
		}
	});
});
