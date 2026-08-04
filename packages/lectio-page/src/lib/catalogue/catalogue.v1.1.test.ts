import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { INTENT_IDS, type IntentId, type PageObject } from '$lib/contract';
import {
	getIntent,
	getObject,
	isSelectable,
	listSelectableIntents,
	type IntentRecord,
	type ObjectRecord
} from '$lib/catalogue';

const root = process.cwd();
const intentCatalogue = JSON.parse(
	readFileSync(join(root, 'contracts/intent-catalogue.v1.json'), 'utf8')
);
const objectCatalogue = JSON.parse(
	readFileSync(join(root, 'contracts/object-catalogue.v1.json'), 'utf8')
);

const PATCHED_INTENTS = [
	'explain',
	'explain-cause',
	'trace-flow',
	'demonstrate',
	'derive',
	'practise-guided',
	'practise-independent',
	'check-understanding',
	'diagnose-misconception',
	'warn',
	'compare'
] as const;

const CAPACITY_OBJECTS = [
	'prose',
	'list',
	'table',
	'figure',
	'aside',
	'worked-example',
	'questions',
	'choices'
] as const;

function hasDensity(value: unknown): boolean {
	if (value == null || typeof value !== 'object') return false;
	if (Array.isArray(value)) return value.some(hasDensity);
	return Object.entries(value as Record<string, unknown>).some(
		([key, child]) => key === 'density' || hasDensity(child)
	);
}

describe('catalogue v1.1 discrimination fields', () => {
	it('bumps both catalogues to 1.1.0', () => {
		expect(intentCatalogue.catalogue_version).toBe('1.1.0');
		expect(objectCatalogue.catalogue_version).toBe('1.1.0');
	});

	it('adds earn/reject/capacity on eight selectable objects only', () => {
		for (const id of CAPACITY_OBJECTS) {
			const record = getObject(id as PageObject) as ObjectRecord;
			expect(record.earns_its_place_when).toBeTruthy();
			expect(record.reject_when).toBeTruthy();
			expect(record.capacity).toBeTruthy();
			expect(typeof record.capacity).toBe('object');
			for (const value of Object.values(record.capacity!)) {
				expect(typeof value).toBe('number');
			}
		}

		for (const id of ['heading', 'answer-key'] as const) {
			const record = getObject(id);
			expect(record?.earns_its_place_when).toBeUndefined();
			expect(record?.reject_when).toBeUndefined();
			expect(record?.capacity).toBeUndefined();
		}

		expect(getObject('aside')?.capacity?.maxPerSection).toBe(2);
	});

	it('adds choose_when/not_when on the eleven co-occurring intents', () => {
		for (const id of PATCHED_INTENTS) {
			const record = getIntent(id) as IntentRecord;
			expect(record.choose_when).toBeTruthy();
			expect(record.not_when).toBeTruthy();
			expect(Object.keys(record.not_when!).length).toBeGreaterThan(0);
		}
	});

	it('marks answer-key as non-selectable without discrimination fields', () => {
		const record = getIntent('answer-key') as IntentRecord;
		expect(record.selectable).toBe(false);
		expect(record.choose_when).toBeUndefined();
		expect(record.not_when).toBeUndefined();
		expect(isSelectable('answer-key')).toBe(false);
		expect(listSelectableIntents()).not.toContain('answer-key');
		expect(listSelectableIntents()).toHaveLength(INTENT_IDS.length - 1);
	});

	it('contains no density field anywhere', () => {
		expect(hasDensity(intentCatalogue)).toBe(false);
		expect(hasDensity(objectCatalogue)).toBe(false);
	});

	it('keeps every not_when key a valid IntentId', () => {
		const valid = new Set<string>(INTENT_IDS);
		for (const id of INTENT_IDS) {
			const record = getIntent(id);
			if (!record?.not_when) continue;
			for (const key of Object.keys(record.not_when)) {
				expect(valid.has(key)).toBe(true);
			}
		}
	});

	it('requires every not_when neighbour to share a valid_object with its parent', () => {
		for (const id of INTENT_IDS) {
			const parent = getIntent(id);
			if (!parent?.not_when) continue;
			const parentObjects = new Set(parent.valid_objects);
			for (const neighbourId of Object.keys(parent.not_when) as IntentId[]) {
				const neighbour = getIntent(neighbourId);
				expect(neighbour).toBeTruthy();
				const shared = neighbour!.valid_objects.some((object) => parentObjects.has(object));
				expect(shared).toBe(true);
			}
		}
	});
});
