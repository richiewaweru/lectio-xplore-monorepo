import { describe, expect, it } from 'vitest';

import {
	adaptV3PackToLectioDocument,
	adaptV3PackToLectioDocumentWithDiagnostics,
	type V3PackDocument
} from './v3-pack-to-lectio-document';

describe('adaptV3PackToLectioDocument', () => {
	it('maps a minimal pack and manifest order', () => {
		const pack: V3PackDocument = {
			generation_id: 'g-1',
			template_id: 'guided-concept-path',
			subject: 'Algebra',
			status: 'final_ready',
			sections: [
				{
					section_id: 'intro_a',
					header: { title: 'Intro', subject: 'Algebra', grade_band: 'secondary' }
				}
			]
		};
		const doc = adaptV3PackToLectioDocument(pack);
		expect(doc.generation_id).toBe('g-1');
		expect(doc.template_id).toBe('guided-concept-path');
		expect(doc.subject).toBe('Algebra');
		expect(doc.status).toBe('completed');
		expect(doc.section_manifest).toEqual([
			{ section_id: 'intro_a', title: 'Intro', position: 1 }
		]);
		expect(doc.sections).toHaveLength(1);
		expect(doc.sections[0].section_id).toBe('intro_a');
		expect(doc.sections[0].template_id).toBe('guided-concept-path');
		expect(doc.sections[0].header?.title).toBe('Intro');
		expect(doc.sections[0].header?.grade_band).toBe('secondary');
	});

	it('fills missing section_id and header defaults', () => {
		const pack: V3PackDocument = {
			subject: 'Science',
			template_id: 'guided-concept-path',
			sections: [{}]
		};
		const doc = adaptV3PackToLectioDocument(pack, { routeGenerationId: 'route-gen' });
		expect(doc.generation_id).toBe('route-gen');
		expect(doc.sections[0].section_id).toBe('section-1');
		expect(doc.sections[0].header?.title).toBeTruthy();
		expect(doc.sections[0].header?.subject).toBe('Science');
		expect(doc.sections[0].header?.grade_band).toBe('secondary');
	});

	it('normalizes invalid grade_band to secondary', () => {
		const pack: V3PackDocument = {
			sections: [
				{
					section_id: 's1',
					header: { title: 'T', subject: 'S', grade_band: 'nope' as unknown as string }
				}
			]
		};
		const doc = adaptV3PackToLectioDocument(pack);
		expect(doc.sections[0].header?.grade_band).toBe('secondary');
	});

	it('maps V3 pack statuses', () => {
		expect(adaptV3PackToLectioDocument({ sections: [], status: 'failed_unusable' }).status).toBe(
			'failed'
		);
		expect(adaptV3PackToLectioDocument({ sections: [], status: 'draft_ready' }).status).toBe(
			'partial'
		);
		expect(adaptV3PackToLectioDocument({ sections: [], status: 'final_with_warnings' }).status).toBe(
			'completed'
		);
		expect(adaptV3PackToLectioDocument({ sections: [], status: 'unknown' }).status).toBe('partial');
		expect(adaptV3PackToLectioDocument({ sections: [], status: 'streaming_preview' }).status).toBe(
			'partial'
		);
	});

	it('returns adapter diagnostics', () => {
		const pack: V3PackDocument = {
			sections: [{ hook: { x: 1 } }, { section_id: 'b', header: { title: 'T', subject: 'S', grade_band: 'primary' } }]
		};
		const { document, diagnostic } = adaptV3PackToLectioDocumentWithDiagnostics(pack);
		expect(document.sections).toHaveLength(2);
		expect(diagnostic.section_count).toBe(2);
		expect(diagnostic.missing_section_ids).toBe(1);
		expect(diagnostic.normalized_header_count).toBe(1);
		expect(diagnostic.fields_by_section[0].fields).toContain('hook');
	});

	it('preserves pack-level answer_key without touching sections', () => {
		const pack: V3PackDocument = {
			sections: [{ section_id: 's1', definition_family: { family_title: 'F', definitions: [] } }],
			answer_key: { entries: [{ question_id: 'q1', student_answer: 'A' }] }
		};
		const doc = adaptV3PackToLectioDocument(pack);
		const s = doc.sections[0] as unknown as Record<string, unknown>;
		expect(s.definition_family).toBeTruthy();
	});

	it('preserves extra section fields', () => {
		const pack: V3PackDocument = {
			sections: [
				{
					section_id: 'x',
					hook: { headline: 'H', body: 'B', anchor: 'A' },
					diagram: { caption: 'Fig', image_url: 'https://example.com/x.png' }
				}
			]
		};
		const doc = adaptV3PackToLectioDocument(pack);
		const s = doc.sections[0] as unknown as Record<string, unknown>;
		expect(s.hook).toEqual({ headline: 'H', body: 'B', anchor: 'A' });
		expect(s.diagram).toEqual({ caption: 'Fig', image_url: 'https://example.com/x.png' });
	});

	it('uses pack template_id for section when section omits it', () => {
		const pack: V3PackDocument = {
			template_id: 'guided-concept-path',
			sections: [{ section_id: 'only' }]
		};
		expect(adaptV3PackToLectioDocument(pack).sections[0].template_id).toBe('guided-concept-path');
	});
});
