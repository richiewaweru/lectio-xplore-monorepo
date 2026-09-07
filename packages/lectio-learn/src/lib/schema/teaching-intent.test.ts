import { describe, expect, it } from 'vitest';

import { PALETTE_GROUPS, componentRegistry, getComponentsByIntent } from './registry';

describe('teaching intent metadata', () => {
	it('maps explain intent to the expected components', () => {
		const explainIds = getComponentsByIntent('explain')
			.map((component) => component.id)
			.sort();

		expect(explainIds).toEqual([
			'callout-block',
			'explanation-block',
			'insight-strip',
			'key-fact'
		]);
	});

	it('assigns teaching intent for every section-backed component', () => {
		for (const component of Object.values(componentRegistry)) {
			if (component.sectionField === null) continue;
			expect(component.teachingIntent, component.id).toBeTruthy();
		}
	});

	it('builds palette groups covering all section-backed component ids', () => {
		const groupedIds = [...new Set(PALETTE_GROUPS.flatMap((group) => group.componentIds))].sort();
		const sectionBackedIds = Object.values(componentRegistry)
			.filter((component) => component.sectionField !== null)
			.map((component) => component.id)
			.sort();

		expect(groupedIds).toEqual(sectionBackedIds);
	});
});

