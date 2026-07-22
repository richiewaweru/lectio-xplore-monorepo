import { describe, expect, it, vi } from 'vitest';

vi.mock('lectio', () => ({
	getEmptyContent: vi.fn(() => ({ body: '' })),
	getEditSchema: vi.fn(() => ({
		component_id: 'explanation-block',
		fields: [
			{ field: 'body', input: 'textarea' },
			{ field: 'title', input: 'text' },
			{ field: 'internal_note', input: 'hidden' }
		]
	}))
}));

import { getEditSchema } from 'lectio';
import { isAiGeneratableComponent, mergeAiContentWithEditableFields } from './ai-block-utils';

describe('mergeAiContentWithEditableFields', () => {
	it('updates only non-hidden edit-schema fields', () => {
		const current = {
			body: 'Existing body',
			title: 'Existing title',
			internal_note: 'Do not touch',
			unmodeled_extra: 'Keep me'
		};
		const generated = {
			body: 'AI body',
			title: 'AI title',
			internal_note: 'AI hidden overwrite',
			another_unknown: 'AI extra'
		};

		const merged = mergeAiContentWithEditableFields('explanation-block', current, generated);
		expect(merged.body).toBe('AI body');
		expect(merged.title).toBe('AI title');
		expect(merged.internal_note).toBe('Do not touch');
		expect(merged.unmodeled_extra).toBe('Keep me');
		expect(merged).not.toHaveProperty('another_unknown');
	});

	it('preserves current content when schema is unavailable', () => {
		vi.mocked(getEditSchema).mockReturnValueOnce(null);
		const current = { body: 'Current body', internal_note: 'Keep' };
		const generated = { body: 'AI body' };
		expect(mergeAiContentWithEditableFields('unknown-component', current, generated)).toEqual(current);
	});

	it('excludes teacher-provided media components from block AI', () => {
		expect(isAiGeneratableComponent('image-block')).toBe(false);
		expect(isAiGeneratableComponent('video-embed')).toBe(false);
		expect(isAiGeneratableComponent('explanation-block')).toBe(true);
	});
});
