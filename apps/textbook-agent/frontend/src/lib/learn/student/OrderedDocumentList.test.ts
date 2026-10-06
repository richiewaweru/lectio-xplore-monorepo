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

describe('figure numbering', () => {
	it('numbers figures cumulatively across sections', () => {
		const document = {
			nodes: [
				{ id: 'f1', kind: 'figure', caption: 'First', alt: 'a', asset_id: 'https://cdn.example.test/a.png' },
				{ id: 'f2', kind: 'figure', caption: 'Second', alt: 'b', asset_id: 'https://cdn.example.test/b.png' }
			],
			sections: [
				{ id: 's1', title: 'One', position: 1, node_ids: ['f1'] },
				{ id: 's2', title: 'Two', position: 2, node_ids: ['f2'] }
			]
		} as unknown as LearnDocument;
		const { container } = render(OrderedDocumentList, { document, preview: true });
		const text = container.querySelector('.lesson-sections')?.textContent ?? '';
		expect(text).toContain('Figure 1');
		expect(text).toContain('Figure 2');
		expect(text.match(/Figure 1/g)?.length).toBe(1);
	});
});
