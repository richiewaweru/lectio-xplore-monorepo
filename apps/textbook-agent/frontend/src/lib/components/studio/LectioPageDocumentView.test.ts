import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { documentRenderVersion, extractLectioDocumentV2 } from '$lib/studio/document-version';
import type { LectioDocument } from '@lectio/page/contract';

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
) as LectioDocument;

describe('LectioPageDocumentView host contract', () => {
	it('accepts canonical v2 fixtures for screen/print routing', () => {
		expect(documentRenderVersion(fixture)).toBe(2);
		const doc = extractLectioDocumentV2(fixture);
		expect(doc?.sections[0]?.title).toBeTruthy();
		expect(doc?.sections[0]?.blocks.map((b) => b.id)).toEqual(
			fixture.sections[0].blocks.map((b) => b.id)
		);
	});
});
