/**
 * Generated views over the Learn capability catalogue.
 *
 * Each view answers one question and carries only what that question needs.
 * The split is not cosmetic: a teaching plan that can see native ids will
 * pre-commit a native path, and a selection request that can see payload
 * schemas and answer keys will start writing content before a form is chosen.
 *
 * Nothing here is hand-maintained. Every view is a pure projection of the
 * capability records, so a record change cannot leave a view stale.
 */

import type { JsonSchema, LearnCapabilityRecord } from './types';

export const TEACHING_VIEW_VERSION = '1.0.0';
export const SELECTION_VIEW_VERSION = '1.0.0';
export const WRITER_VIEW_VERSION = '1.0.0';
export const RUNTIME_VIEW_VERSION = '1.0.0';

/** A capability a consumer may actually select and run today. */
export function isSelectable(record: LearnCapabilityRecord): boolean {
	return record.availability === 'available' && record.readiness === 'generation-ready';
}

// ── Teaching view ───────────────────────────────────────────────────────────

export interface LearnTeachingCoverage {
	intent: string;
	/** True only when at least one selectable capability serves the intent. */
	supported_today: boolean;
	learner_actions: string[];
}

/**
 * What Learn can teach, in shared vocabulary only.
 *
 * Deliberately absent: capability ids, component ids, interaction kinds,
 * schemas, capacities and renderer references. A shared teaching plan built
 * from this view cannot name Learn inventory, so it cannot exclude Print.
 */
export interface LearnTeachingView {
	view: 'teaching';
	view_version: string;
	native_path: 'learn';
	coverage: LearnTeachingCoverage[];
	/** Actions Learn can satisfy today, across every selectable capability. */
	supported_actions: string[];
}

export function buildTeachingView(records: LearnCapabilityRecord[]): LearnTeachingView {
	const byIntent = new Map<string, { supported: boolean; actions: Set<string> }>();

	for (const record of records) {
		const selectable = isSelectable(record);
		for (const intent of record.supported_intents) {
			const entry = byIntent.get(intent) ?? { supported: false, actions: new Set<string>() };
			entry.supported = entry.supported || selectable;
			if (selectable) for (const action of record.supported_actions) entry.actions.add(action);
			byIntent.set(intent, entry);
		}
	}

	const supported = new Set<string>();
	for (const record of records) {
		if (!isSelectable(record)) continue;
		for (const action of record.supported_actions) supported.add(action);
	}

	return {
		view: 'teaching',
		view_version: TEACHING_VIEW_VERSION,
		native_path: 'learn',
		coverage: [...byIntent.entries()]
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([intent, entry]) => ({
				intent,
				supported_today: entry.supported,
				learner_actions: [...entry.actions].sort()
			})),
		supported_actions: [...supported].sort()
	};
}

// ── Selection view ──────────────────────────────────────────────────────────

export interface LearnSelectionRecord {
	id: string;
	kind: LearnCapabilityRecord['kind'];
	purpose: string;
	cognitive_job: string;
	supported_intents: string[];
	supported_actions: string[];
	choose_when: string;
	reject_when: string;
	prerequisites: string[];
	capacity: Record<string, number>;
	evaluation_mode: LearnCapabilityRecord['evaluation']['mode'];
	partial_scoring: boolean;
	requires_asset: boolean;
	presentation_variants: string[];
}

/**
 * Enough to choose a capability, and no more.
 *
 * Deliberately absent: `payload_schema`, `field_guidance`, `examples` and every
 * answer-bearing config key. A selector that can already see the answer key is
 * writing content, not selecting a form.
 */
export interface LearnSelectionView {
	view: 'selection';
	view_version: string;
	/** Only capabilities a consumer may select today. */
	capabilities: LearnSelectionRecord[];
	/** Everything excluded, with the reason and the route back. */
	excluded: Array<{
		id: string;
		readiness: LearnCapabilityRecord['readiness'];
		availability: LearnCapabilityRecord['availability'];
		blocking_reasons: string[];
		path_to_readiness: string[];
	}>;
}

function toSelectionRecord(record: LearnCapabilityRecord): LearnSelectionRecord {
	return {
		id: record.id,
		kind: record.kind,
		purpose: record.purpose,
		cognitive_job: record.cognitive_job,
		supported_intents: [...record.supported_intents],
		supported_actions: [...record.supported_actions],
		choose_when: record.choose_when,
		reject_when: record.reject_when,
		prerequisites: [...record.prerequisites],
		capacity: { ...record.capacity },
		evaluation_mode: record.evaluation.mode,
		partial_scoring: record.evaluation.partial_scoring,
		requires_asset: record.asset_requirements !== null,
		presentation_variants: [...record.presentation_variants]
	};
}

export function buildSelectionView(records: LearnCapabilityRecord[]): LearnSelectionView {
	return {
		view: 'selection',
		view_version: SELECTION_VIEW_VERSION,
		capabilities: records.filter(isSelectable).map(toSelectionRecord),
		excluded: records
			.filter((record) => !isSelectable(record))
			.map((record) => ({
				id: record.id,
				readiness: record.readiness,
				availability: record.availability,
				blocking_reasons: [...record.blocking_reasons],
				path_to_readiness: [...record.path_to_readiness]
			}))
	};
}

// ── Writer view ─────────────────────────────────────────────────────────────

export interface LearnWriterRecord {
	id: string;
	purpose: string;
	payload_schema_ref: string;
	payload_schema: JsonSchema;
	field_guidance: Record<string, string>;
	requires: string[];
	capacity: Record<string, number>;
	negative_cases: string[];
	examples: unknown[];
	asset_requirements: LearnCapabilityRecord['asset_requirements'];
	source_refs: string[];
}

/**
 * The exact payload contract for a chosen capability.
 *
 * Kept separate from selection so a writer request carries the schema for the
 * one capability that was selected, never the whole catalogue.
 */
export interface LearnWriterView {
	view: 'writer';
	view_version: string;
	capabilities: Record<string, LearnWriterRecord>;
}

export function buildWriterView(records: LearnCapabilityRecord[]): LearnWriterView {
	const capabilities: Record<string, LearnWriterRecord> = {};
	for (const record of records) {
		capabilities[record.id] = {
			id: record.id,
			purpose: record.purpose,
			payload_schema_ref: record.payload_schema_ref,
			payload_schema: record.payload_schema,
			field_guidance: { ...record.field_guidance },
			requires: [...record.requires],
			capacity: { ...record.capacity },
			negative_cases: [...record.negative_cases],
			examples: record.examples,
			asset_requirements: record.asset_requirements,
			source_refs: [
				record.readiness_evidence.source_path,
				record.payload_schema_ref,
				...(record.evaluation.contract_ref ? [record.evaluation.contract_ref] : [])
			]
		};
	}
	return { view: 'writer', view_version: WRITER_VIEW_VERSION, capabilities };
}

// ── Runtime view ────────────────────────────────────────────────────────────

export interface LearnRuntimeRecord {
	id: string;
	kind: LearnCapabilityRecord['kind'];
	renderer_ref: string;
	response_schema: JsonSchema | null;
	evaluation: LearnCapabilityRecord['evaluation'];
	default_behaviour: Record<string, unknown>;
	allowed_config: Record<string, string>;
	accessibility: LearnCapabilityRecord['accessibility'];
}

/**
 * What a runtime needs to render a capability, collect a response and evaluate
 * it. Carries the response schema and the evaluator identity, not the authored
 * payload guidance.
 */
export interface LearnRuntimeView {
	view: 'runtime';
	view_version: string;
	capabilities: Record<string, LearnRuntimeRecord>;
}

export function buildRuntimeView(records: LearnCapabilityRecord[]): LearnRuntimeView {
	const capabilities: Record<string, LearnRuntimeRecord> = {};
	for (const record of records) {
		capabilities[record.id] = {
			id: record.id,
			kind: record.kind,
			renderer_ref: record.renderer_ref,
			response_schema: record.response_schema,
			evaluation: { ...record.evaluation },
			default_behaviour: { ...record.default_behaviour },
			allowed_config: { ...record.allowed_config },
			accessibility: { ...record.accessibility }
		};
	}
	return { view: 'runtime', view_version: RUNTIME_VIEW_VERSION, capabilities };
}
