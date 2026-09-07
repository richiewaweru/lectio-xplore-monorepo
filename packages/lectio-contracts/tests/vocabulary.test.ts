import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
	INSTRUCTIONAL_INTENT_IDS,
	INSTRUCTIONAL_INTENT_SOURCE,
	getInstructionalIntent,
	instructionalIntentRecords,
	isInstructionalIntentId,
	listIntentBoundaries,
	listTeachingSelectableIntentIds
} from '../src/intents';
import { LEARNER_ACTION_IDS } from '../src/actions';

const pageCatalogue = JSON.parse(
	readFileSync(
		join(import.meta.dirname, '../../lectio-page/contracts/intent-catalogue.v1.json'),
		'utf8'
	)
) as {
	catalogue_version: string;
	intents: Record<
		string,
		{
			teacher_label: string;
			pedagogical_role: string;
			cognitive_job: string;
			valid_objects: string[];
			not_when?: Record<string, string>;
			choose_when?: string;
			selectable?: boolean;
		}
	>;
};

describe('instructional intent vocabulary is a faithful copy of the canonical Print catalogue', () => {
	it('preserves all 32 canonical intent ids in catalogue order', () => {
		const canonical = Object.keys(pageCatalogue.intents);
		expect(canonical).toHaveLength(32);
		expect(INSTRUCTIONAL_INTENT_IDS).toEqual(canonical);
	});

	it('pins the source catalogue revision it was generated from', () => {
		expect(INSTRUCTIONAL_INTENT_SOURCE.package).toBe('@lectio/page');
		expect(INSTRUCTIONAL_INTENT_SOURCE.catalogue_version).toBe(pageCatalogue.catalogue_version);
	});

	it('copies label, role, cognitive job, choose_when and boundaries verbatim', () => {
		for (const [id, sourceRecord] of Object.entries(pageCatalogue.intents)) {
			const record = getInstructionalIntent(id);
			expect(record, `intent ${id} missing from shared vocabulary`).toBeDefined();
			expect(record!.label).toBe(sourceRecord.teacher_label);
			expect(record!.pedagogical_role).toBe(sourceRecord.pedagogical_role);
			expect(record!.cognitive_job).toBe(sourceRecord.cognitive_job);
			expect(record!.choose_when).toBe(sourceRecord.choose_when ?? null);
			expect(record!.boundaries).toEqual(sourceRecord.not_when ?? {});
			expect(record!.teaching_selectable).toBe(sourceRecord.selectable !== false);
		}
	});

	it('every boundary references a real intent id', () => {
		for (const id of INSTRUCTIONAL_INTENT_IDS) {
			for (const boundary of listIntentBoundaries(id)) {
				expect(
					isInstructionalIntentId(boundary.intent),
					`intent ${id} names unknown neighbour ${boundary.intent}`
				).toBe(true);
				expect(boundary.intent).not.toBe(id);
			}
		}
	});

	it('drops native inventory: no record carries valid_objects or generation guidance', () => {
		for (const [id, record] of Object.entries(instructionalIntentRecords)) {
			const keys = Object.keys(record as unknown as Record<string, unknown>);
			expect(keys, `intent ${id}`).toEqual([
				'label',
				'pedagogical_role',
				'cognitive_job',
				'choose_when',
				'boundaries',
				'teaching_selectable'
			]);
		}
	});

	it('marks answer-key as native-derived rather than teaching-selectable', () => {
		expect(getInstructionalIntent('answer-key')?.teaching_selectable).toBe(false);
		expect(listTeachingSelectableIntentIds()).toHaveLength(31);
		expect(listTeachingSelectableIntentIds()).not.toContain('answer-key');
	});

	it('exports the learner actions the pack requires by id', () => {
		for (const required of [
			'order-items',
			'complete-missing-values',
			'select-one',
			'select-many',
			'match-pairs',
			'classify-items',
			'enter-number',
			'enter-text',
			'identify-region',
			'place-labels',
			'compare-without-response'
		]) {
			expect(LEARNER_ACTION_IDS, `missing learner action ${required}`).toContain(required);
		}
	});
});
