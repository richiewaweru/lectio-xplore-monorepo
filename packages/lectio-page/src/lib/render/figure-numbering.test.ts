import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import LectioDocumentView from './LectioDocumentView.svelte';
import type { DocumentBlock, LectioDocument } from '../contract/document';

function figure(id: string, caption: string): DocumentBlock {
	return {
		id,
		object: 'figure',
		intent: 'show-structure',
		position: 0,
		content: { alt_text: 'alt', caption, asset: { status: 'pending', request_id: id } }
	} as DocumentBlock;
}

describe('figure numbering across sections', () => {
	it('numbers figures cumulatively over sections', () => {
		const doc = {
			document_version: 2,
			contract_version: '1.0.0',
			id: 'fig-test',
			title: 'Figures',
			language: 'en',
			metadata: {},
			sections: [
				{ id: 's1', title: 'One', blocks: [figure('f1', 'First')] },
				{ id: 's2', title: 'Two', blocks: [figure('f2', 'Second')] }
			]
		} as LectioDocument;
		const { container } = render(LectioDocumentView, { document: doc });
		const labels = [...container.querySelectorAll('.lectio-figure-number')].map((n) =>
			n.textContent?.trim()
		);
		expect(labels).toEqual(['Figure 1.', 'Figure 2.']);
	});
});
