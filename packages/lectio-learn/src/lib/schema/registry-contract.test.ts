import { describe, expect, it } from 'vitest';

import { componentRegistry } from './registry';

describe('registry contract metadata', () => {
	it('requires generationHint for every mapped section field component', () => {
		for (const component of Object.values(componentRegistry)) {
			if (component.sectionField === null) continue;
			expect(component.generationHint?.trim(), `${component.id} is missing generationHint`).toBeTruthy();
		}
	});
});
