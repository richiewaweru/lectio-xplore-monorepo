import { render, screen, within } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import OrderedDocumentList from './OrderedDocumentList.svelte';
import type { LearnDocument } from '$lib/learn/document/types';

const longTitle = 'How a plant makes its own food: photosynthesis in the leaves';

describe('lesson map', () => {
	it('keeps the full long title text in a wrapping map item', () => {
		const document = {
			nodes: [],
			sections: [{ id: 's1', title: longTitle, position: 1, node_ids: [] }]
		} as unknown as LearnDocument;
		render(OrderedDocumentList, { document, preview: true });
		const label = within(screen.getByTestId('runtime-section-tabs')).getByText(longTitle);
		expect(label.closest('button')?.textContent).toContain(longTitle);
		expect(label.closest('li')).toBeTruthy();
	});
});
