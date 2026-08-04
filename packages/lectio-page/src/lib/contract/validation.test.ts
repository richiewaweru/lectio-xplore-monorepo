import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
	assertValidDocument,
	validateDocument,
	validateSemantics,
	validateStructure
} from './validation';
import type { LectioDocument } from './document';
import { wordCount } from '../utils/rich-text';

const root = process.cwd();

function loadFixture(name: string): LectioDocument {
	return JSON.parse(readFileSync(join(root, 'fixtures', name), 'utf8'));
}

describe('schema + semantic validation', () => {
	it('accepts fixtures structurally and semantically', () => {
		for (const name of ['empty-document.json', 'photosynthesis-ref.json']) {
			const doc = loadFixture(name);
			expect(validateStructure(doc)).toEqual([]);
			expect(validateDocument(doc).filter((i) => i.severity === 'error')).toEqual([]);
			expect(() => assertValidDocument(doc)).not.toThrow();
		}
	});

	it('rejects wrong object content via schema', () => {
		const doc = loadFixture('empty-document.json');
		(doc.sections[0].blocks[1] as { content: unknown }).content = { banana: true };
		const issues = validateStructure(doc);
		expect(issues.some((i) => i.code === 'schema')).toBe(true);
	});

	it('rejects position mismatch after commit', () => {
		const doc = loadFixture('empty-document.json');
		doc.sections[0].blocks[1].position = 99;
		const issues = validateSemantics(doc);
		expect(issues.some((i) => i.code === 'position-mismatch')).toBe(true);
	});

	it('rejects trailing and consecutive headings', () => {
		const doc = loadFixture('empty-document.json');
		doc.sections[0].blocks = [
			{
				id: 'h1',
				object: 'heading',
				position: 0,
				intent: undefined,
				content: { level: 2, text: 'Alone' }
			}
		];
		expect(validateSemantics(doc).some((i) => i.code === 'heading-trailing')).toBe(true);

		doc.sections[0].blocks = [
			{
				id: 'h1',
				object: 'heading',
				position: 0,
				intent: undefined,
				content: { level: 2, text: 'A' }
			},
			{
				id: 'h2',
				object: 'heading',
				position: 1,
				intent: undefined,
				content: { level: 2, text: 'B' }
			},
			{
				id: 'p1',
				object: 'prose',
				intent: 'orient',
				position: 2,
				content: { paragraphs: ['ok'] }
			}
		];
		expect(validateSemantics(doc).some((i) => i.code === 'heading-consecutive')).toBe(true);
	});

	it('rejects heading bound only to a margin aside', () => {
		const doc = loadFixture('empty-document.json');
		doc.sections[0].blocks = [
			{
				id: 'h1',
				object: 'heading',
				position: 0,
				intent: undefined,
				content: { level: 2, text: 'Tip' }
			},
			{
				id: 'a1',
				object: 'aside',
				intent: 'warn',
				position: 1,
				layout: { placement: 'margin' },
				content: { body: 'Margin note' }
			}
		];
		expect(validateSemantics(doc).some((i) => i.code === 'heading-margin-aside')).toBe(true);
	});

	it('counts aside words from visible text only', () => {
		const rich = [
			{ type: 'text' as const, value: 'one two three' },
			{ type: 'strong' as const, children: [{ type: 'text' as const, value: ' four five' }] }
		];
		expect(wordCount(rich)).toBe(5);
		expect(wordCount('six seven')).toBe(2);
	});

	it('rejects unknown answer-key references and duplicates', () => {
		const doc = loadFixture('photosynthesis-ref.json');
		doc.answer_key!.content.groups[0].entries.push({
			question_id: 'missing-q',
			answer: 'nope'
		});
		expect(validateSemantics(doc).some((i) => i.code === 'answer-key-ref')).toBe(true);

		doc.answer_key!.content.groups[0].entries = [
			{ question_id: 'q1', answer: 'a' },
			{ question_id: 'q1', answer: 'b' }
		];
		expect(validateSemantics(doc).some((i) => i.code === 'answer-key-duplicate')).toBe(true);
	});

	it('assertValidDocument throws on errors', () => {
		expect(() => assertValidDocument({ banana: true })).toThrow(/Invalid LectioDocument/);
	});

	it('warns when aside count exceeds catalogue maxPerSection', () => {
		const doc = loadFixture('empty-document.json');
		doc.sections[0].blocks = [
			{
				id: 'h1',
				object: 'heading',
				position: 0,
				intent: undefined,
				content: { level: 2, text: 'Tips' }
			},
			{
				id: 'p1',
				object: 'prose',
				intent: 'orient',
				position: 1,
				content: { paragraphs: ['Anchor paragraph for three asides.'] }
			},
			{
				id: 'a1',
				object: 'aside',
				intent: 'warn',
				position: 2,
				layout: { placement: 'margin' },
				content: { body: 'One' }
			},
			{
				id: 'a2',
				object: 'aside',
				intent: 'emphasise',
				position: 3,
				layout: { placement: 'margin' },
				content: { body: 'Two' }
			},
			{
				id: 'a3',
				object: 'aside',
				intent: 'memory-aid',
				position: 4,
				layout: { placement: 'margin' },
				content: { body: 'Three' }
			}
		];
		const issues = validateSemantics(doc);
		expect(issues.some((i) => i.code === 'aside-density' && i.severity === 'warning')).toBe(true);
	});

	it('warns on undersized list, table, and choices', () => {
		const doc = loadFixture('empty-document.json');
		doc.sections[0].blocks = [
			{
				id: 'h1',
				object: 'heading',
				position: 0,
				intent: undefined,
				content: { level: 2, text: 'Short forms' }
			},
			{
				id: 'l1',
				object: 'list',
				intent: 'summarise',
				position: 1,
				content: {
					style: 'unordered',
					items: [{ text: 'Only one' }, { text: 'Only two' }]
				}
			},
			{
				id: 't1',
				object: 'table',
				intent: 'compare',
				position: 2,
				content: {
					columns: [{ id: 'a', label: 'A' }],
					rows: [{ cells: { a: 'one' } }],
					presentation: 'standard'
				}
			},
			{
				id: 'c1',
				object: 'choices',
				intent: 'check-understanding',
				position: 3,
				content: {
					stem: 'Pick one',
					options: [
						{ letter: 'A', text: 'Yes' },
						{ letter: 'B', text: 'No' }
					]
				}
			}
		];
		const issues = validateSemantics(doc);
		expect(issues.some((i) => i.code === 'list-too-short' && i.severity === 'warning')).toBe(true);
		expect(issues.some((i) => i.code === 'table-too-narrow' && i.severity === 'warning')).toBe(true);
		expect(issues.some((i) => i.code === 'table-too-short' && i.severity === 'warning')).toBe(true);
		expect(issues.some((i) => i.code === 'choices-too-few' && i.severity === 'warning')).toBe(true);
	});
});
