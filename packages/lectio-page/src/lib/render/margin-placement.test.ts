import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/svelte';
import BlockView from './BlockView.svelte';
import { validateDocument } from '../contract/validation';
import type { DocumentBlock, LectioDocument } from '../contract/document';

function asideBlock(layout?: DocumentBlock['layout']): DocumentBlock {
	return {
		id: 'a1',
		object: 'aside',
		intent: 'warn',
		position: 0,
		layout,
		content: { body: 'note' }
	};
}

function listBlock(layout?: DocumentBlock['layout']): DocumentBlock {
	return {
		id: 'l1',
		object: 'list',
		intent: 'summarise',
		position: 0,
		layout,
		content: { style: 'unordered', items: [{ text: 'item' }] }
	};
}

function baseDoc(block: DocumentBlock): LectioDocument {
	return {
		document_version: 2,
		contract_version: '1.0.0',
		id: 'margin-placement-test',
		title: 'Margin placement',
		language: 'en',
		metadata: {},
		sections: [{ id: 's1', title: 'Section', blocks: [block] }]
	};
}

describe('margin placement rendering', () => {
	it('aside with no layout renders lectio-block--margin (default preserves current behaviour)', () => {
		const { container } = render(BlockView, { block: asideBlock(undefined) });
		expect(container.querySelector('.lectio-aside.lectio-block--margin')).not.toBeNull();
	});

	it('aside with placement: main does not render lectio-block--margin', () => {
		const { container } = render(BlockView, {
			block: asideBlock({ placement: 'main' })
		});
		const aside = container.querySelector('.lectio-aside');
		expect(aside).not.toBeNull();
		expect(aside?.classList.contains('lectio-block--margin')).toBe(false);
	});

	it('list with placement: margin renders lectio-block--margin on the ul/ol', () => {
		const { container } = render(BlockView, {
			block: listBlock({ placement: 'margin' })
		});
		expect(container.querySelector('.lectio-list.lectio-block--margin')).not.toBeNull();
	});

	it('list with no layout does not render lectio-block--margin', () => {
		const { container } = render(BlockView, { block: listBlock(undefined) });
		const list = container.querySelector('.lectio-list');
		expect(list).not.toBeNull();
		expect(list?.classList.contains('lectio-block--margin')).toBe(false);
	});

	it('prose with placement: margin is rejected by validateDocument', () => {
		const proseBlock: DocumentBlock = {
			id: 'p1',
			object: 'prose',
			intent: 'orient',
			position: 0,
			layout: { placement: 'margin' },
			content: { paragraphs: ['Body'] }
		};
		const issues = validateDocument(baseDoc(proseBlock));
		expect(issues.some((i) => i.code === 'layout-placement')).toBe(true);
	});
});
