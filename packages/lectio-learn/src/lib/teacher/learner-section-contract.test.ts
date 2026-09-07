import { describe, expect, it } from 'vitest';

import { calculusSection } from '../dev/dummy-content';
import {
	assertNoLearnerStateOnSection,
	fromSectionContents,
	learnerSectionLabel,
	orderedDocumentSections,
	withDefaultLearnerSectionMeta,
	type DocumentSection
} from './document';

describe('learner section contract (Phase 03)', () => {
	it('orders sections canonically by position then id', () => {
		const doc = fromSectionContents([calculusSection], {
			title: 'T',
			subject: 'Mathematics',
			preset_id: 'blue-classroom'
		});
		doc.sections = [
			{ ...doc.sections[0], id: 'b', position: 2, title: 'B' },
			{ id: 'a', template_id: 'open-canvas', block_ids: [], title: 'A', position: 1 },
			{ id: 'c', template_id: 'open-canvas', block_ids: [], title: 'C', position: 1 }
		];
		const ordered = orderedDocumentSections(doc).map((s) => s.id);
		expect(ordered).toEqual(['a', 'c', 'b']);
	});

	it('defaults learner labels without writing runtime state', () => {
		const section: DocumentSection = {
			id: 's1',
			template_id: 'guided-concept-path',
			block_ids: [],
			title: 'Photosynthesis',
			position: 0
		};
		const enriched = withDefaultLearnerSectionMeta(section);
		expect(learnerSectionLabel(enriched)).toBe('Photosynthesis');
		expect(enriched.assessment_mode).toBe('ungraded-info');
		expect(enriched.concept_refs).toEqual([]);
		expect(assertNoLearnerStateOnSection(enriched)).toEqual([]);
	});

	it('rejects accidental learner runtime keys on sections', () => {
		const dirty = {
			id: 's1',
			template_id: 'open-canvas',
			block_ids: [],
			title: 'X',
			position: 0,
			score: 0.9
		} as unknown as DocumentSection;
		expect(assertNoLearnerStateOnSection(dirty)).toContain(
			'Learner runtime key "score" must not appear on DocumentSection.'
		);
	});

	it('preserves authored practice/graded designation', () => {
		const section: DocumentSection = {
			id: 's1',
			template_id: 'open-canvas',
			block_ids: [],
			title: 'Check',
			position: 0,
			learner_label: 'Check-in',
			assessment_mode: 'graded',
			learner_intent: 'check',
			concept_refs: [{ concept_id: 'c1', role: 'assess' }]
		};
		const enriched = withDefaultLearnerSectionMeta(section);
		expect(enriched.learner_label).toBe('Check-in');
		expect(enriched.assessment_mode).toBe('graded');
		expect(enriched.concept_refs?.[0]?.concept_id).toBe('c1');
	});
});
