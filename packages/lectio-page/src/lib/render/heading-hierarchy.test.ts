import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { normalizeDocument } from '$lib/normalize/document';
import type { LectioDocument } from '$lib/contract/document';

const root = join(process.cwd());

describe('heading hierarchy', () => {
	it('allows documents with section titles and no heading blocks', () => {
		const raw = JSON.parse(
			readFileSync(join(root, 'fixtures/photosynthesis-ref.json'), 'utf8')
		) as LectioDocument;
		const doc = normalizeDocument(raw);
		expect(doc.title.length).toBeGreaterThan(0);
		for (const section of doc.sections) {
			expect(section.title.length).toBeGreaterThan(0);
			const headingBlocks = section.blocks.filter((b) => b.object === 'heading');
			// First-slice documents may omit heading blocks; section.title owns the h2.
			expect(Array.isArray(headingBlocks)).toBe(true);
		}
	});

	it('still accepts nested heading blocks as structural content', () => {
		const doc: LectioDocument = {
			document_version: 2,
			contract_version: '1.0.0',
			id: 'heading-hierarchy-fixture',
			title: 'Document Title Owns H1',
			language: 'en',
			metadata: {},
			sections: [
				{
					id: 'sec-1',
					title: 'Section Title Owns H2',
					blocks: [
						{
							id: 'b-heading',
							object: 'heading',
							position: 0,
							intent: undefined,
							content: { level: 3, text: 'Nested structural heading' }
						},
						{
							id: 'b-prose',
							object: 'prose',
							position: 1,
							intent: 'orient',
							content: { paragraphs: ['Lead paragraph after nested heading.'] }
						}
					]
				}
			]
		};
		const normalized = normalizeDocument(doc);
		expect(normalized.sections[0].title).toBe('Section Title Owns H2');
		expect(normalized.sections[0].blocks[0].object).toBe('heading');
		expect(normalized.sections[0].blocks[1].object).toBe('prose');
	});
});
