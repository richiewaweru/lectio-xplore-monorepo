// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$lib/learn/authoring/builder/api/lesson-crud', () => ({
	getBuilderLesson: vi.fn(),
	updateBuilderLesson: vi.fn()
}));

import DocumentEditor from './DocumentEditor.svelte';
import { SECTION_HIGHLIGHT_CLASS } from '$lib/curriculum/lessons/section-focus';
import type { LearnDocument } from './types';

function doc(): LearnDocument {
	return {
		version: 2,
		id: 'doc-1',
		title: 'Fractions',
		subject: 'mathematics',
		source: 'manual',
		nodes: [
			{ id: 'n1', kind: 'paragraph', text: 'Warm up text' },
			{ id: 'n2', kind: 'paragraph', text: 'Worked example text' }
		],
		sections: [
			{ id: 'sec-a', title: 'Warm up', position: 0, node_ids: ['n1'] },
			{ id: 'sec-b', title: 'Worked example', position: 1, node_ids: ['n2'] }
		],
		created_at: '2026-01-01T00:00:00.000Z',
		updated_at: '2026-01-01T00:00:00.000Z'
	};
}

describe('DocumentEditor ?section= focus', () => {
	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it('opens the requested section and highlights it', async () => {
		Element.prototype.scrollIntoView = vi.fn();
		render(DocumentEditor, { props: { document: doc(), focusSectionId: 'sec-b' } });

		const tab = await waitFor(() => screen.getByRole('button', { name: 'Worked example' }));
		await waitFor(() => expect(tab.classList.contains('active')).toBe(true));
		const wrap = await waitFor(() => {
			const el = document.querySelector<HTMLElement>('[data-section-id="sec-b"]');
			expect(el).toBeTruthy();
			return el!;
		});
		await waitFor(() => expect(wrap.classList.contains(SECTION_HIGHLIGHT_CLASS)).toBe(true));
		expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
		expect(screen.queryByText('Warm up text')).toBeNull();
	});

	it('ignores an unknown section and shows all sections', () => {
		render(DocumentEditor, { props: { document: doc(), focusSectionId: 'nope' } });
		expect(screen.getByRole('button', { name: 'All' }).classList.contains('active')).toBe(true);
		expect(document.querySelector('[data-section-id]')).toBeNull();
	});
});
