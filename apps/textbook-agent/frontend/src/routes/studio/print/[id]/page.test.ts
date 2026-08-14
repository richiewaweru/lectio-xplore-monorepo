import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const source = readFileSync(join(process.cwd(), 'src/routes/studio/print/[id]/+page.svelte'), 'utf8');

describe('native print edition contract', () => {
	it('reads the authoritative edition query and passes it to the V2 renderer', () => {
		expect(source).toContain("page.url.searchParams.get('edition') === 'student'");
		expect(source).toContain('<LectioPageDocumentView document={pageDocumentV2} {edition} />');
		expect(source).not.toContain('<LectioPageDocumentView document={pageDocumentV2} edition="teacher" />');
	});

	it('blocks native print while required visuals are pending or flagged', () => {
		expect(source).toContain('fetchNativeGenerationDetail(generationId, headers)');
		expect(source).toContain('apiFetch(');
		expect(source).toContain('Authorization = `Bearer ${token}`');
		expect(source).toContain('Native visuals are not ready for print. Retry visuals from Studio before exporting.');
		expect(source).toContain('hasRetryableVisualQuality(detail.visual_quality)');
	});
});
