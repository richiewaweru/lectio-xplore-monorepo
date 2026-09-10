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

describe('instructional intent vocabulary is owned by @lectio/contracts', () => {
	it('preserves all 32 canonical intent ids', () => {
		expect(INSTRUCTIONAL_INTENT_IDS).toHaveLength(32);
	});

	it('pins ownership to @lectio/contracts', () => {
		expect(INSTRUCTIONAL_INTENT_SOURCE.package).toBe('@lectio/contracts');
		expect(INSTRUCTIONAL_INTENT_SOURCE.file).toBe('data/instructional-intents.v1.json');
	});

	it('Print catalogue adapts the same intent ids (no local invent)', () => {
		const pageIds = Object.keys(pageCatalogue.intents);
		expect(pageIds.sort()).toEqual([...INSTRUCTIONAL_INTENT_IDS].sort());
		for (const id of INSTRUCTIONAL_INTENT_IDS) {
			const shared = getInstructionalIntent(id)!;
			const page = pageCatalogue.intents[id]!;
			expect(page, `Print missing shared intent ${id}`).toBeDefined();
			expect(page.teacher_label).toBe(shared.label);
			expect(page.pedagogical_role).toBe(shared.pedagogical_role);
			expect(page.cognitive_job).toBe(shared.cognitive_job);
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
