import { describe, expect, it } from 'vitest';

import {
	addParagraph,
	deleteNode,
	moveNodeDown,
	moveNodeUp,
	reorderNode,
	updateListItems,
	updateNodeText
} from './document-state';
import type { LearnDocument } from './types';

function sampleDoc(): LearnDocument {
	return {
		version: 2,
		id: 'doc-1',
		title: 'Fractions',
		subject: 'mathematics',
		source: 'manual',
		nodes: [
			{ id: 'n1', kind: 'paragraph', text: 'First' },
			{ id: 'n2', kind: 'heading', text: 'Section', level: 2 },
			{ id: 'n3', kind: 'list', ordered: false, items: ['a', 'b'] },
			{
				id: 'n4',
				kind: 'interaction',
				interaction_type: 'choice',
				prompt: 'Pick one'
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
		expect(next!.nodes[0]).toMatchObject({ id: 'n1', kind: 'paragraph', text: 'Updated first' });
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

	it('reorders nodes up and down by id without changing other content', () => {
		const doc = sampleDoc();
		const up = moveNodeUp(doc, 'n2');
		expect(up!.nodes.map((n) => n.id)).toEqual(['n2', 'n1', 'n3', 'n4']);
		expect(up!.nodes[0]).toMatchObject({ text: 'Section' });

		const down = moveNodeDown(doc, 'n1');
		expect(down!.nodes.map((n) => n.id)).toEqual(['n2', 'n1', 'n3', 'n4']);

		const noop = reorderNode(doc, 'n1', 'up');
		expect(noop!.nodes.map((n) => n.id)).toEqual(['n1', 'n2', 'n3', 'n4']);

		const missing = reorderNode(doc, 'missing', 'down');
		expect(missing).toBeNull();
	});

	it('adds a paragraph after a node and deletes by id', () => {
		const doc = sampleDoc();
		const withPara = addParagraph(doc, 'Inserted', 'n1');
		expect(withPara.nodes.map((n) => n.id)[0]).toBe('n1');
		expect(withPara.nodes[1]).toMatchObject({ kind: 'paragraph', text: 'Inserted' });
		expect(withPara.nodes).toHaveLength(5);

		const removed = deleteNode(withPara, withPara.nodes[1]!.id);
		expect(removed!.nodes.map((n) => n.id)).toEqual(['n1', 'n2', 'n3', 'n4']);
		expect(deleteNode(doc, 'nope')).toBeNull();
	});
});
