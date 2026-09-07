import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { documentRenderVersion, extractLectioDocumentV2 } from './document-version';

const fixture = JSON.parse(
	readFileSync(
		join(
			process.cwd(),
			'..',
			'backend',
			'tests',
			'fixtures',
			'lectio-page',
			'valid-document.json'
		),
		'utf8'
	)
);

describe('document version routing', () => {
	it('detects v2 documents', () => {
		expect(documentRenderVersion(fixture)).toBe(2);
		const doc = extractLectioDocumentV2(fixture);
		expect(doc?.title).toContain('Plants');
		expect(doc?.sections[0].blocks.length).toBeGreaterThan(0);
	});

	it('keeps legacy packs on v1', () => {
		expect(documentRenderVersion({ kind: 'v3_booklet_pack', sections: [] })).toBe(1);
		expect(extractLectioDocumentV2({ kind: 'v3_booklet_pack', sections: [] })).toBeNull();
	});

	it('reads nested lectio_document envelopes', () => {
		const envelope = { document_version: 2, lectio_document: fixture };
		expect(documentRenderVersion(envelope)).toBe(2);
		expect(extractLectioDocumentV2(envelope)?.id).toBe(fixture.id);
	});
});
