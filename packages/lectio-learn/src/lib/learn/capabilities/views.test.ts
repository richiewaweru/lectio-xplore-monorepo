// @vitest-environment node

/**
 * P01-K06: the generated views must stay separated.
 *
 * The point of the split is that a consumer cannot see what it has no business
 * seeing at that step. So these tests do not check that the views were built —
 * they check what each view *cannot* contain.
 */

import { describe, expect, it } from 'vitest';

import {
	identifierShapedNativeIds,
	isInstructionalIntentId,
	isLearnerActionId
} from '@lectio/contracts';
import {
	buildRuntimeView,
	buildSelectionView,
	buildTeachingView,
	buildWriterView,
	isSelectable
} from './views';
import { learnCapabilities, validateCapabilityRecords } from './index';

const records = learnCapabilities;

function jsonKeysAndStrings(value: unknown): { keys: string[]; strings: string[] } {
	const keys: string[] = [];
	const strings: string[] = [];
	const walk = (node: unknown): void => {
		if (Array.isArray(node)) {
			node.forEach(walk);
			return;
		}
		if (node && typeof node === 'object') {
			for (const [key, child] of Object.entries(node)) {
				keys.push(key);
				walk(child);
			}
			return;
		}
		if (typeof node === 'string') strings.push(node);
	};
	walk(value);
	return { keys, strings };
}

describe('capability catalogue integrity', () => {
	it('declares nothing it cannot back with evidence', () => {
		expect(validateCapabilityRecords(records)).toEqual([]);
	});

	it('covers every interaction kind exactly once', () => {
		const interactionIds = records
			.filter((record) => record.kind === 'interaction')
			.map((record) => record.id)
			.sort();
		expect(interactionIds).toEqual([
			'choice',
			'classify',
			'drag-label',
			'fill-blank',
			'image-hotspot',
			'match-pairs',
			'multi-select',
			'numeric',
			'sequence',
			'short-response'
		]);
	});

	it('treats image-choice as a presentation variant, not a kind', () => {
		expect(records.some((record) => record.id === 'image-choice')).toBe(false);
		const choice = records.find((record) => record.id === 'choice');
		expect(choice?.presentation_variants).toContain('image');
	});

	it('keeps the spatial kinds unavailable while authoring is missing', () => {
		for (const id of ['image-hotspot', 'drag-label']) {
			const record = records.find((entry) => entry.id === id);
			expect(record?.availability, id).toBe('unavailable');
			expect(record?.readiness, id).not.toBe('generation-ready');
			expect(record?.blocking_reasons.join(' '), id).toMatch(/coordinate|region|asset/i);
			expect(record?.path_to_readiness.length, id).toBeGreaterThan(0);
		}
	});

	it('does not let an unwired interaction claim generation-ready', () => {
		for (const record of records.filter((entry) => entry.kind === 'interaction')) {
			expect(record.readiness, record.id).not.toBe('generation-ready');
			expect(record.readiness_evidence.consumer_selection_support, record.id).toBe(false);
		}
	});
});

describe('teaching view carries no native inventory (P01-K06)', () => {
	const view = buildTeachingView(records);
	const { keys, strings } = jsonKeysAndStrings(view);

	it('names only canonical intents and learner actions', () => {
		for (const entry of view.coverage) {
			expect(isInstructionalIntentId(entry.intent), entry.intent).toBe(true);
			for (const action of entry.learner_actions) {
				expect(isLearnerActionId(action), action).toBe(true);
			}
		}
		for (const action of view.supported_actions) {
			expect(isLearnerActionId(action), action).toBe(true);
		}
	});

	it('names no capability, component or interaction kind', () => {
		const catalogueIds = new Set(records.map((record) => record.id));
		const shared = new Set(['classify', 'sequence', 'match-pairs', 'compare', 'define', 'explain']);
		for (const value of [...keys, ...strings]) {
			if (shared.has(value)) continue;
			expect(catalogueIds.has(value), `teaching view names capability "${value}"`).toBe(false);
		}
		for (const nativeId of identifierShapedNativeIds()) {
			expect(
				JSON.stringify(view).includes(nativeId),
				`teaching view leaks native id "${nativeId}"`
			).toBe(false);
		}
	});

	it('carries no schema, capacity, renderer or answer detail', () => {
		for (const banned of [
			'payload_schema',
			'response_schema',
			'capacity',
			'renderer_ref',
			'field_guidance',
			'examples',
			'evaluation',
			'answers',
			'correct_option_id',
			'correct_option_ids'
		]) {
			expect(keys, `teaching view carries "${banned}"`).not.toContain(banned);
		}
	});

	it('reports an intent as supported only when a selectable capability serves it', () => {
		const selectableIntents = new Set(
			records.filter(isSelectable).flatMap((record) => record.supported_intents)
		);
		for (const entry of view.coverage) {
			expect(entry.supported_today, entry.intent).toBe(selectableIntents.has(entry.intent));
		}
	});
});

describe('selection view stops at selection (P01-K06)', () => {
	const view = buildSelectionView(records);
	const { keys } = jsonKeysAndStrings(view);

	it('offers only capabilities that are selectable today', () => {
		expect(view.capabilities.length).toBeGreaterThan(0);
		for (const offered of view.capabilities) {
			const record = records.find((entry) => entry.id === offered.id);
			expect(record?.readiness, offered.id).toBe('generation-ready');
			expect(record?.availability, offered.id).toBe('available');
		}
	});

	it('omits every incomplete, unavailable and manual-only capability', () => {
		const offered = new Set(view.capabilities.map((entry) => entry.id));
		for (const record of records.filter((entry) => !isSelectable(entry))) {
			expect(offered.has(record.id), `${record.id} is offered but not selectable`).toBe(false);
		}
		// And each one is still accounted for, with a reason and a route back.
		const excluded = new Map(view.excluded.map((entry) => [entry.id, entry]));
		for (const record of records.filter((entry) => !isSelectable(entry))) {
			const entry = excluded.get(record.id);
			expect(entry, record.id).toBeDefined();
			expect(entry!.blocking_reasons.length, record.id).toBeGreaterThan(0);
			expect(entry!.path_to_readiness.length, record.id).toBeGreaterThan(0);
		}
	});

	it('carries no payload schema, writer guidance, example or answer key', () => {
		for (const banned of [
			'payload_schema',
			'payload_schema_ref',
			'field_guidance',
			'examples',
			'negative_cases',
			'response_schema',
			'answers',
			'accepted_answers',
			'correct_option_id',
			'correct_option_ids',
			'order',
			'pairs'
		]) {
			expect(keys, `selection view carries "${banned}"`).not.toContain(banned);
		}
	});

	it('still carries what a selector actually needs', () => {
		for (const offered of view.capabilities) {
			expect(offered.purpose.length).toBeGreaterThan(0);
			expect(offered.choose_when.length).toBeGreaterThan(0);
			expect(offered.reject_when.length).toBeGreaterThan(0);
			expect(offered.supported_intents.length).toBeGreaterThan(0);
		}
	});
});

describe('writer and runtime views', () => {
	it('writer view resolves a payload contract per capability', () => {
		const view = buildWriterView(records);
		for (const record of records) {
			const entry = view.capabilities[record.id];
			expect(entry, record.id).toBeDefined();
			expect(entry!.payload_schema_ref, record.id).toBe(record.payload_schema_ref);
			expect(entry!.source_refs.length, record.id).toBeGreaterThan(0);
		}
	});

	it('writer view gives per-field guidance for every interaction payload field', () => {
		const view = buildWriterView(records);
		for (const record of records.filter((entry) => entry.kind === 'interaction')) {
			const schema = record.payload_schema as {
				properties?: Record<string, unknown>;
				oneOf?: Array<{ properties?: Record<string, unknown> }>;
			};
			const fields = new Set([
				...Object.keys(schema.properties ?? {}),
				...(schema.oneOf ?? []).flatMap((branch) => Object.keys(branch.properties ?? {}))
			]);
			const guidance = view.capabilities[record.id]!.field_guidance;
			for (const field of fields) {
				expect(guidance[field], `${record.id}.${field} has no writer guidance`).toBeTruthy();
			}
		}
	});

	it('runtime view names an evaluator wherever it claims auto-scoring', () => {
		const view = buildRuntimeView(records);
		for (const entry of Object.values(view.capabilities)) {
			if (entry.evaluation.mode !== 'auto-score') continue;
			expect(entry.evaluation.contract_ref, entry.id).toBeTruthy();
			expect(entry.response_schema, entry.id).not.toBeNull();
		}
	});

	it('runtime view carries no authored writer guidance', () => {
		const { keys } = jsonKeysAndStrings(buildRuntimeView(records));
		for (const banned of ['field_guidance', 'examples', 'negative_cases', 'choose_when']) {
			expect(keys, `runtime view carries "${banned}"`).not.toContain(banned);
		}
	});
});
