import { describe, expect, it } from 'vitest';
import { buildRenderUnits, normalizeDocument, NormalizeError } from '../normalize/document';
import { validateSemantics } from '../contract/validation';
import type { DocumentBlock, LectioDocument } from '../contract/document';

function prose(id: string, position: number): DocumentBlock {
	return {
		id,
		object: 'prose',
		intent: 'orient',
		position,
		content: { paragraphs: [`Body ${id}`] }
	};
}

function heading(id: string, position: number, text = 'Title'): DocumentBlock {
	return {
		id,
		object: 'heading',
		position,
		intent: undefined,
		content: { level: 2, text }
	};
}

function baseDoc(blocks: DocumentBlock[]): LectioDocument {
	return {
		document_version: 2,
		contract_version: '1.0.0',
		id: 'order-test',
		title: 'Order',
		language: 'en',
		metadata: {},
		sections: [{ id: 's1', title: 'Nav only', blocks }]
	};
}

describe('normalize + heading binding', () => {
	it('sorts out-of-order positions then rewrites contiguous indexes', () => {
		const doc = baseDoc([prose('p2', 5), prose('p1', 1), heading('h1', 0)]);
		const normalized = normalizeDocument(doc);
		expect(normalized.sections[0].blocks.map((b) => b.id)).toEqual(['h1', 'p1', 'p2']);
		expect(normalized.sections[0].blocks.map((b) => b.position)).toEqual([0, 1, 2]);
	});

	it('stable-sorts equal positions by id', () => {
		const doc = baseDoc([prose('b', 0), prose('a', 0)]);
		const normalized = normalizeDocument(doc);
		expect(normalized.sections[0].blocks.map((b) => b.id)).toEqual(['a', 'b']);
	});

	it('throws on duplicate block ids', () => {
		const doc = baseDoc([prose('x', 0), prose('x', 1)]);
		expect(() => normalizeDocument(doc)).toThrow(NormalizeError);
	});

	it('builds heading bindings without sorting', () => {
		const cases: Array<{ lead: DocumentBlock; object: string }> = [
			{
				object: 'prose',
				lead: prose('p', 1)
			},
			{
				object: 'figure',
				lead: {
					id: 'f',
					object: 'figure',
					intent: 'show-structure',
					position: 1,
					content: { alt_text: 'alt', asset: { status: 'pending', request_id: 'r1' } }
				}
			},
			{
				object: 'table',
				lead: {
					id: 't',
					object: 'table',
					intent: 'compare',
					position: 1,
					content: {
						columns: [{ id: 'c', label: 'C' }],
						rows: [{ cells: { c: 'v' } }]
					}
				}
			},
			{
				object: 'worked-example',
				lead: {
					id: 'w',
					object: 'worked-example',
					intent: 'demonstrate',
					position: 1,
					content: {
						problem: 'P',
						steps: [{ text: 'S' }],
						answer: 'A'
					}
				}
			},
			{
				object: 'questions',
				lead: {
					id: 'q',
					object: 'questions',
					intent: 'practise-guided',
					position: 1,
					content: { items: [{ id: 'q1', prompt: 'Q?' }] }
				}
			}
		];

		for (const { lead, object } of cases) {
			const units = buildRenderUnits([heading('h', 0), lead]);
			expect(units).toHaveLength(1);
			expect(units[0]).toMatchObject({
				kind: 'heading-binding',
				heading: { id: 'h' },
				lead: { object }
			});
		}
	});

	it('does not re-sort when building units', () => {
		// Deliberately wrong positions relative to array order — render trusts array order.
		const units = buildRenderUnits([
			prose('first', 9),
			heading('h', 0),
			prose('second', 1)
		]);
		expect(units.map((u) => (u.kind === 'block' ? u.block.id : u.heading.id))).toEqual([
			'first',
			'h'
		]);
		expect(units[1]).toMatchObject({ kind: 'heading-binding', lead: { id: 'second' } });
	});

	it('rejects consecutive, trailing, and margin-aside heading sequences', () => {
		expect(
			validateSemantics(
				baseDoc([heading('h1', 0), heading('h2', 1), prose('p', 2)])
			).some((i) => i.code === 'heading-consecutive')
		).toBe(true);

		expect(
			validateSemantics(baseDoc([heading('h1', 0)])).some((i) => i.code === 'heading-trailing')
		).toBe(true);

		expect(
			validateSemantics(
				baseDoc([
					heading('h1', 0),
					{
						id: 'a1',
						object: 'aside',
						intent: 'warn',
						position: 1,
						layout: { placement: 'margin' },
						content: { body: 'note' }
					}
				])
			).some((i) => i.code === 'heading-margin-aside')
		).toBe(true);
	});
});
