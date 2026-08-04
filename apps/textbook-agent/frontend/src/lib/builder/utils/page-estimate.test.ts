import { describe, expect, it } from 'vitest';
import type { BlockInstance } from 'lectio';
import { estimatePageCount, pageWarningLevel, pageWarningMessage } from './page-estimate';

function block(component_id: string): BlockInstance {
	return {
		id: crypto.randomUUID(),
		component_id,
		content: {},
		position: 0
	};
}

describe('page-estimate', () => {
	it('estimates at least one A4 page and uses component height estimates', () => {
		expect(estimatePageCount([])).toBe(1);
		expect(estimatePageCount([block('practice-stack'), block('diagram-series'), block('comparison-grid')])).toBe(2);
	});

	it('classifies page warning levels', () => {
		expect(pageWarningLevel(4)).toBe('none');
		expect(pageWarningLevel(5)).toBe('info');
		expect(pageWarningLevel(7)).toBe('warn');
	});

	it('returns warning copy only above the focus threshold', () => {
		expect(pageWarningMessage(4)).toBeNull();
		expect(pageWarningMessage(5)).toContain('5 A4 pages');
		expect(pageWarningMessage(7)).toContain('under 4 pages');
	});
});
