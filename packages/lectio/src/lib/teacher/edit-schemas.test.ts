import { describe, expect, it } from 'vitest';

import { getEditSchema } from './edit-schemas';
import { getComponentFieldMap } from '../schema/registry';

describe('edit-schemas', () => {
	it('returns a schema for every component with a section field', () => {
		const map = getComponentFieldMap();
		for (const componentId of Object.keys(map)) {
			const schema = getEditSchema(componentId);
			expect(schema, componentId).not.toBeNull();
			expect(schema!.component_id).toBe(componentId);
			expect(schema!.fields.length).toBeGreaterThan(0);
		}
	});

	it('returns null for glossary-inline (no block field)', () => {
		expect(getEditSchema('glossary-inline')).toBeNull();
	});

	it('exposes full table editing for comparison grids', () => {
		const schema = getEditSchema('comparison-grid');
		expect(schema?.fields.map((field) => field.field)).toEqual([
			'title',
			'intro',
			'columns',
			'rows',
			'apply_prompt'
		]);

		const rows = schema?.fields.find((field) => field.field === 'rows');
		expect(rows?.itemSchema?.find((field) => field.field === 'values')?.input).toBe('object-list');
	});

	it('exposes definition entries and fill-in-blank word bank fields', () => {
		expect(getEditSchema('definition-family')?.fields.some((field) => field.field === 'definitions')).toBe(
			true
		);
		expect(getEditSchema('fill-in-blank')?.fields.map((field) => field.field)).toEqual([
			'instruction',
			'segments',
			'word_bank'
		]);
	});

	it('exposes media picker fields for diagram editing', () => {
		const blockSchema = getEditSchema('diagram-block');
		expect(blockSchema?.fields.map((field) => field.field)).toEqual(
			expect.arrayContaining(['media_id', 'image_url', 'svg_content', 'width'])
		);
		expect(blockSchema?.fields.find((field) => field.field === 'media_id')?.input).toBe('media');

		const compareSchema = getEditSchema('diagram-compare');
		expect(compareSchema?.fields.map((field) => field.field)).toEqual(
			expect.arrayContaining(['before_media_id', 'after_media_id', 'before_svg', 'after_svg'])
		);
		expect(compareSchema?.fields.find((field) => field.field === 'before_media_id')?.input).toBe(
			'media'
		);
		expect(compareSchema?.fields.find((field) => field.field === 'after_media_id')?.input).toBe(
			'media'
		);

		const seriesFrames = getEditSchema('diagram-series')?.fields.find(
			(field) => field.field === 'diagrams'
		);
		expect(seriesFrames?.itemSchema?.map((field) => field.field)).toEqual(
			expect.arrayContaining(['media_id', 'image_url', 'svg_content'])
		);
		expect(seriesFrames?.itemSchema?.find((field) => field.field === 'media_id')?.input).toBe(
			'media'
		);
	});
});
