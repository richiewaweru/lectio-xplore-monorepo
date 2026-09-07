import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { buildTeachingView } from '../src/teaching-view';
import {
	NATIVE_DETAIL_KEYS,
	identifierShapedNativeIds,
	nativeInventoryIds
} from '../src/native-inventory';
import { LEARNER_ACTION_IDS, listSpatialActionIds } from '../src/actions';
import { listTeachingSelectableIntentIds } from '../src/intents';

const generatedPath = join(import.meta.dirname, '../generated/teaching-view.v1.json');

function collectKeys(value: unknown, into = new Set<string>()): Set<string> {
	if (Array.isArray(value)) {
		for (const item of value) collectKeys(item, into);
	} else if (value && typeof value === 'object') {
		for (const [key, child] of Object.entries(value)) {
			into.add(key);
			collectKeys(child, into);
		}
	}
	return into;
}

function collectStrings(value: unknown, into: string[] = []): string[] {
	if (typeof value === 'string') into.push(value);
	else if (Array.isArray(value)) for (const item of value) collectStrings(item, into);
	else if (value && typeof value === 'object')
		for (const child of Object.values(value)) collectStrings(child, into);
	return into;
}

describe('P01-K06 — teaching view carries no native inventory', () => {
	const view = buildTeachingView();

	it('exposes only teaching-selectable intents and the full action vocabulary', () => {
		expect(view.view).toBe('teaching');
		expect(view.intents.map((intent) => intent.id)).toEqual(listTeachingSelectableIntentIds());
		expect(view.learner_actions.map((action) => action.id)).toEqual(LEARNER_ACTION_IDS);
	});

	it('has no key that carries native schema, capacity or layout detail', () => {
		const keys = collectKeys(view);
		for (const banned of NATIVE_DETAIL_KEYS) {
			expect(keys.has(banned), `teaching view leaks native key "${banned}"`).toBe(false);
		}
	});

	it('records expose exactly the teaching fields and nothing more', () => {
		for (const intent of view.intents) {
			expect(Object.keys(intent).sort()).toEqual([
				'boundaries',
				'choose_when',
				'cognitive_job',
				'id',
				'label',
				'pedagogical_role'
			]);
		}
		for (const action of view.learner_actions) {
			expect(Object.keys(action).sort()).toEqual([
				'id',
				'label',
				'learner_does',
				'requires_response'
			]);
		}
	});

	it('never uses a native inventory id as a key or as a whole value', () => {
		const keys = collectKeys(view);
		const values = new Set(collectStrings(view));
		for (const nativeId of nativeInventoryIds()) {
			expect(keys.has(nativeId), `teaching view keys on native id "${nativeId}"`).toBe(false);
			expect(values.has(nativeId), `teaching view value equals native id "${nativeId}"`).toBe(
				false
			);
		}
	});

	it('never mentions an identifier-shaped native id in free text', () => {
		const haystack = collectStrings(view);
		for (const nativeId of identifierShapedNativeIds()) {
			const offender = haystack.find((text) => text.toLowerCase().includes(nativeId));
			expect(
				offender,
				`teaching view mentions native inventory id "${nativeId}" in: ${offender}`
			).toBeUndefined();
		}
	});

	it('every boundary points at an intent that is itself in the view', () => {
		const present = new Set(view.intents.map((intent) => intent.id));
		for (const intent of view.intents) {
			for (const boundary of intent.boundaries) {
				expect(
					present.has(boundary.intent),
					`${intent.id} boundary names ${boundary.intent}, which the teaching view does not expose`
				).toBe(true);
			}
		}
	});

	it('declares which actions need a learner response and which are passive', () => {
		const passive = view.learner_actions.filter((action) => !action.requires_response);
		expect(passive.map((action) => action.id)).toContain('compare-without-response');
		const spatial = listSpatialActionIds();
		expect(spatial).toEqual(['identify-region', 'place-labels']);
	});

	it('P01-K01 — the committed generated copy equals a fresh build', () => {
		const committed = JSON.parse(readFileSync(generatedPath, 'utf8'));
		expect(committed).toEqual(JSON.parse(JSON.stringify(view)));
	});

	it('P01-K01 — regeneration is deterministic', () => {
		expect(JSON.stringify(buildTeachingView())).toBe(JSON.stringify(buildTeachingView()));
	});
});
