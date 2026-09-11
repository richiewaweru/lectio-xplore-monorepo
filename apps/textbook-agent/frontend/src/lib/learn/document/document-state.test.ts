import { describe, expect, it } from 'vitest';

import {
	addNode,
	addParagraph,
	deleteNode,
	moveNodeDown,
	moveNodeUp,
	reorderNode,
	updateCallout,
	updateFigure,
	updateListItems,
	updateNodeText,
	updateTable
} from './document-state';
import type { LearnDocument } from './types';
import { resolveAssetUrl } from './resolve-asset';

function sampleDoc(): LearnDocument {
	return {
		version: 2,
		id: 'doc-1',
		title: 'Fractions',
		subject: 'mathematics',
		source: 'manual',
		nodes: [
			{ id: 'n1', kind: 'paragraph', text: 'First', teaching_block_id: 'tb-1' },
			{ id: 'n2', kind: 'heading', text: 'Section', level: 2 },
			{ id: 'n3', kind: 'list', ordered: false, items: ['a', 'b'] },
			{
				id: 'n4',
				kind: 'interaction',
				interaction_type: 'choice',
				prompt: 'Pick one'
			},
			{
				id: 'n5',
				kind: 'table',
				headers: ['A', 'B'],
				rows: [['1', '2']],
				caption: 'Nums'
			},
			{
				id: 'n6',
				kind: 'callout',
				tone: 'tip',
				title: 'Tip',
				body: 'Remember'
			},
			{
				id: 'n7',
				kind: 'figure',
				asset_id: 'demo.png',
				caption: 'Cap',
				alt: 'Alt'
			}
		],
		created_at: '2026-09-10T00:00:00.000Z',
		updated_at: '2026-09-10T00:00:00.000Z'
	};
}

describe('learn document-state', () => {
	it('updates paragraph and heading text by stable id', () => {
		const doc = sampleDoc();
		const next = updateNodeText(doc, 'n1', 'Updated first');
		expect(next).not.toBeNull();
		expect(next!.nodes[0]).toMatchObject({
			id: 'n1',
			kind: 'paragraph',
			text: 'Updated first',
			teaching_block_id: 'tb-1'
		});
		expect(doc.nodes[0]).toMatchObject({ text: 'First' });

		const headed = updateNodeText(next!, 'n2', 'New heading');
		expect(headed!.nodes[1]).toMatchObject({ id: 'n2', text: 'New heading' });
	});

	it('updates interaction prompt and list items separately', () => {
		const doc = sampleDoc();
		const prompted = updateNodeText(doc, 'n4', 'New prompt');
		expect(prompted!.nodes[3]).toMatchObject({
			kind: 'interaction',
			prompt: 'New prompt'
		});
		expect(updateNodeText(doc, 'n3', 'ignored')).toBeNull();

		const listed = updateListItems(doc, 'n3', ['x', 'y', 'z']);
		expect(listed!.nodes[2]).toMatchObject({
			kind: 'list',
			items: ['x', 'y', 'z']
		});
	});

	it('updates table cells, figure caption, and callout body', () => {
		const doc = sampleDoc();
		const tabled = updateTable(doc, 'n5', {
			rows: [['3', '4']],
			headers: ['X', 'Y'],
			caption: 'Updated'
		});
		expect(tabled!.nodes[4]).toMatchObject({
			kind: 'table',
			headers: ['X', 'Y'],
			rows: [['3', '4']],
			caption: 'Updated'
		});

		const figured = updateFigure(doc, 'n7', { caption: 'New cap', asset_id: '/images/a.png' });
		expect(figured!.nodes[6]).toMatchObject({
			kind: 'figure',
			caption: 'New cap',
			asset_id: '/images/a.png',
			alt: 'Alt'
		});

		const called = updateCallout(doc, 'n6', { body: 'Updated tip', tone: 'warning' });
		expect(called!.nodes[5]).toMatchObject({
			kind: 'callout',
			body: 'Updated tip',
			tone: 'warning',
			title: 'Tip'
		});
	});

	it('reorders nodes up and down by id without changing other content', () => {
		const doc = sampleDoc();
		const up = moveNodeUp(doc, 'n2');
		expect(up!.nodes.map((n) => n.id).slice(0, 4)).toEqual(['n2', 'n1', 'n3', 'n4']);
		expect(up!.nodes[0]).toMatchObject({ text: 'Section' });

		const down = moveNodeDown(doc, 'n1');
		expect(down!.nodes.map((n) => n.id).slice(0, 4)).toEqual(['n2', 'n1', 'n3', 'n4']);

		const noop = reorderNode(doc, 'n1', 'up');
		expect(noop!.nodes.map((n) => n.id)[0]).toBe('n1');

		const missing = reorderNode(doc, 'missing', 'down');
		expect(missing).toBeNull();
	});

	it('adds any primitive kind and deletes by id', () => {
		const doc = sampleDoc();
		const withPara = addParagraph(doc, 'Inserted', 'n1');
		expect(withPara.nodes.map((n) => n.id)[0]).toBe('n1');
		expect(withPara.nodes[1]).toMatchObject({ kind: 'paragraph', text: 'Inserted' });
		expect(withPara.nodes).toHaveLength(8);

		const withHeading = addNode(doc, 'heading', 'n2');
		expect(withHeading.nodes[2]).toMatchObject({ kind: 'heading' });

		const removed = deleteNode(withPara, withPara.nodes[1]!.id);
		expect(removed!.nodes.map((n) => n.id)).toEqual([
			'n1',
			'n2',
			'n3',
			'n4',
			'n5',
			'n6',
			'n7'
		]);
		expect(deleteNode(doc, 'nope')).toBeNull();
	});

	it('resolves figure asset ids to image urls', () => {
		expect(resolveAssetUrl('https://cdn.example/a.png')).toBe('https://cdn.example/a.png');
		expect(resolveAssetUrl('/images/a.png')).toBe('/images/a.png');
		expect(resolveAssetUrl('gen/figure.png')).toBe('/images/gen/figure.png');
		expect(resolveAssetUrl('m1', { m1: { url: 'https://cdn.example/m1.png' } })).toBe(
			'https://cdn.example/m1.png'
		);
		expect(resolveAssetUrl(null)).toBeNull();
	});
});
