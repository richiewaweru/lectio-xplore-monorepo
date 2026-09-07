import { describe, expect, it } from 'vitest';

import { filterPaletteGroups } from './palette-overlay';

describe('palette overlay grouping', () => {
	it('returns intent groups with components when query is empty', () => {
		const groups = filterPaletteGroups('');
		expect(groups.length).toBeGreaterThan(0);
		const practiceGroup = groups.find((entry) => entry.group.id === 4);
		expect(practiceGroup).toBeTruthy();
		expect(practiceGroup?.components.some((component) => component.id === 'practice-stack')).toBe(true);
	});

	it('filters across labels, descriptions, and ids', () => {
		const byId = filterPaletteGroups('practice-stack');
		expect(byId.some((entry) => entry.components.some((component) => component.id === 'practice-stack'))).toBe(
			true
		);

		const noMatch = filterPaletteGroups('zzzz-no-match');
		expect(noMatch).toHaveLength(0);
	});
});
