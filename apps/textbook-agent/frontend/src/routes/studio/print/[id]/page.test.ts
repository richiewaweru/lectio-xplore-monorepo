import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const source = readFileSync(join(process.cwd(), 'src/routes/studio/print/[id]/+page.svelte'), 'utf8');

describe('native print edition contract', () => {
	it('reads the authoritative edition query and passes it to the V2 renderer', () => {
		expect(source).toContain("page.url.searchParams.get('edition') === 'student'");
		expect(source).toContain('<LectioPageDocumentView document={pageDocumentV2} {edition} />');
		expect(source).toContain('PrintDocumentEditor');
		expect(source).not.toContain('<LectioPageDocumentView document={pageDocumentV2} edition="teacher" />');
	});

	it('honours ?section= by scrolling to and highlighting the section once rendered', () => {
		expect(source).toContain("page.url.searchParams.get('section')");
		expect(source).toContain('focusSectionWhenReady(target)');
		const editor = readFileSync(
			join(process.cwd(), 'src/lib/print/components/studio/PrintDocumentEditor.svelte'),
			'utf8'
		);
		expect(editor).toContain('data-section-id={section.id}');
		const view = readFileSync(
			join(process.cwd(), 'src/lib/print/components/studio/LectioPageDocumentView.svelte'),
			'utf8'
		);
		expect(view).toContain('dataset.sectionId');
	});

	it('blocks native print while required visuals are pending or flagged', () => {
		expect(source).toContain('fetchNativeGenerationDetail(generationId, headers)');
		expect(source).toContain('apiFetch(');
		expect(source).toContain('Authorization = `Bearer ${token}`');
		expect(source).toContain('Native visuals are not ready for print. Retry visuals from Studio before exporting.');
		expect(source).toContain('hasRetryableVisualQuality(detail.visual_quality)');
	});
});
