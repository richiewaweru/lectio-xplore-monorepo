import { describe, expect, it } from 'vitest';
import {
	PATH_INDEPENDENCE_COPY,
	generatePathLabel,
	openPathLabel,
	pathHasRealization
} from './path-generation';

describe('path-generation helpers', () => {
	it('states that Print and Learn are independent from the Teaching Plan', () => {
		expect(PATH_INDEPENDENCE_COPY).toBe(
			'Print and Learn are generated independently from the Teaching Plan.'
		);
		expect(PATH_INDEPENDENCE_COPY.toLowerCase()).not.toMatch(/convert/);
	});

	it('labels Generate / Open actions per path', () => {
		expect(generatePathLabel('print')).toBe('Generate Print');
		expect(generatePathLabel('learn')).toBe('Generate Learn');
		expect(openPathLabel('print')).toBe('Open Print');
		expect(openPathLabel('learn')).toBe('Open Learn');
	});

	it('detects existing realizations without implying conversion', () => {
		expect(
			pathHasRealization({ print_open_href: '/studio/print/g1' }, 'print')
		).toBe(true);
		expect(pathHasRealization({ print_open_href: '/studio/print/g1' }, 'learn')).toBe(false);
		expect(pathHasRealization({ learn_realization_id: 'r1' }, 'learn')).toBe(true);
	});
});
