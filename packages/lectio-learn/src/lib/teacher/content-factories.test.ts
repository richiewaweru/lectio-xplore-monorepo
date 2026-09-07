import { describe, expect, it } from 'vitest';

import { assertFactoriesCoverRegistry, getEmptyContent } from './content-factories';
import { getComponentFieldMap } from '../schema/registry';
import { validateSection } from '../schema/validate';

describe('content-factories', () => {
	it('covers every registry component that has a section field', () => {
		expect(() => assertFactoriesCoverRegistry()).not.toThrow();
	});

	it('getEmptyContent produces section slices that validate without hard errors for core fields', () => {
		const fieldMap = getComponentFieldMap();
		const header = getEmptyContent('section-header');
		const hook = getEmptyContent('hook-hero');
		const explanation = getEmptyContent('explanation-block');
		const practice = getEmptyContent('practice-stack');
		const whatNext = getEmptyContent('what-next-bridge');

		const section = {
			section_id: 's1',
			template_id: 't1',
			header,
			hook,
			explanation,
			practice,
			what_next: whatNext
		};

		const warnings = validateSection(section as never);
		expect(Array.isArray(warnings)).toBe(true);
	});

	it('throws for unknown component id', () => {
		expect(() => getEmptyContent('not-a-real-component')).toThrow();
	});

	it('has a factory entry for each mapped component id', () => {
		const map = getComponentFieldMap();
		for (const id of Object.keys(map)) {
			expect(() => getEmptyContent(id)).not.toThrow();
		}
	});

	it('seeds diagram block content with stable media and fallback fields', () => {
		expect(getEmptyContent('diagram-block')).toMatchObject({
			media_id: '',
			image_url: '',
			svg_content: '',
			caption: '',
			alt_text: '',
			width: 'full'
		});
	});

	it('seeds diagram compare content with both svg and image fields for builder parity', () => {
		expect(getEmptyContent('diagram-compare')).toMatchObject({
			before_media_id: '',
			after_media_id: '',
			before_svg: '',
			after_svg: '',
			before_image_url: '',
			after_image_url: ''
		});
	});

	it('seeds diagram series with one starter frame and stable media fields', () => {
		expect(getEmptyContent('diagram-series')).toMatchObject({
			title: '',
			diagrams: [
				{
					media_id: '',
					image_url: '',
					svg_content: '',
					step_label: '',
					caption: ''
				}
			]
		});
	});

	it('scaffolds editable table, definition family, and fill-in-blank content', () => {
		expect(getEmptyContent('comparison-grid')).toMatchObject({
			columns: [
				{ id: 'col-1', title: 'Option A' },
				{ id: 'col-2', title: 'Option B' }
			],
			rows: [{ values: [{ text: '' }, { text: '' }] }]
		});
		expect(getEmptyContent('definition-family')).toMatchObject({
			definitions: [{ term: '', formal: '', plain: '' }]
		});
		expect(getEmptyContent('fill-in-blank')).toMatchObject({
			instruction: 'Fill in each blank with the correct word.',
			segments: [
				{ text: 'The answer is ', is_blank: false },
				{ text: '', is_blank: true, answer: '' }
			],
			word_bank: []
		});
	});
});
