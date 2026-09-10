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

import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import type { JsonSchema, LearnCapabilityRecord } from './types';

export const TEACHING_VIEW_VERSION = '1.0.0';
export const SELECTION_VIEW_VERSION = '1.0.0';
export const WRITER_VIEW_VERSION = '2.0.0';
export const RUNTIME_VIEW_VERSION = '1.0.0';
export const AUTHORING_DEFINITION_VERSION = '2.0.0';

type AuthoringMode = 'generate' | 'convert-approved';

export type KnowledgePolicy = 'supplied_only' | 'supplied_preferred' | 'objective_development';
export type AssessmentPolicy = 'automatic_required' | 'automatic_preferred' | 'teacher_review';

export interface KnowledgePolicySpec {
	default: KnowledgePolicy;
	supported: KnowledgePolicy[];
}

export interface AssessmentPolicySpec {
	default: AssessmentPolicy;
	supported: AssessmentPolicy[];
	teacher_review_permitted: boolean;
}

/** Core interactions that author a full activity envelope in generate mode. */
export const CORE_INTERACTION_ENVELOPE_IDS = new Set([
	'choice',
	'multi-select',
	'fill-blank',
	'numeric',
	'short-response',
	'match-pairs',
	'classify',
	'sequence'
]);

export interface AuthoringInstructions {
	resource_ref: string;
	text: string;
}

const LEARN_INSTRUCTION_RESOURCE_IDS = new Set([
	'choice',
	'multi-select',
	'fill-blank',
	'numeric',
	'short-response',
	'match-pairs',
	'classify',
	'sequence',
	'section-header',
	'hook-hero',
	'explanation-block',
	'definition-card',
	'key-fact',
	'callout-block',
	'process-steps',
	'worked-example-card',
	'summary-block',
	'timeline-block',
	'diagram-compare',
	'quiz-check',
	'fill-in-blank',
	'answer-key',
	'comparison-grid',
	'definition-family',
	'diagram-block',
	'diagram-series',
	'glossary-rail',
	'insight-strip',
	'interview-anchor',
	'pitfall-alert',
	'practice-stack',
	'prerequisite-strip',
	'reflection-prompt',
	'section-divider',
	'short-answer',
	'student-textbox',
	'what-next-bridge'
]);

const REGISTERED_VALIDATOR_REFS = new Set([
	'learn.payload_schema',
	'learn.evaluateChoice',
	'learn.evaluateMultiSelect',
	'learn.evaluateFillBlank',
	'learn.evaluateNumeric',
	'learn.evaluateShortResponse',
	'learn.evaluateMatchPairs',
	'learn.evaluateSequence',
	'learn.quizContentToInteractionContract',
	'learn.fillBlankContentToInteractionContract'
]);

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

/** Generate-mode envelope: student prompt + runtime config + feedback. */
export function buildAuthoringEnvelopeSchema(configSchema: JsonSchema): JsonSchema {
	return {
		type: 'object',
		required: ['prompt', 'config', 'feedback'],
		additionalProperties: true,
		properties: {
			prompt: { type: 'string', minLength: 1 },
			config: configSchema,
			feedback: {
				type: 'object',
				required: ['correct', 'incorrect'],
				additionalProperties: false,
				properties: {
					correct: { type: 'string' },
					incorrect: { type: 'string' },
					partial: { type: 'string' }
				}
			}
		}
	};
}

function envelopeFieldGuidance(
	record: LearnCapabilityRecord,
	configGuidance: Record<string, string>
): Record<string, string> {
	return {
		prompt:
			'Student-facing question or instruction. Use plain language the learner reads directly; do not copy the planning brief.',
		'feedback.correct': 'Short message shown when the learner answer is fully correct.',
		'feedback.incorrect': 'Short message shown when the learner answer is wrong or incomplete.',
		'feedback.partial':
			'Optional message when partial credit applies; omit when the interaction does not support partial scoring.',
		...Object.fromEntries(
			Object.entries(configGuidance).map(([key, value]) => [`config.${key}`, value])
		)
	};
}

function writerPayloadSchema(record: LearnCapabilityRecord): JsonSchema {
	if (record.kind === 'interaction' && CORE_INTERACTION_ENVELOPE_IDS.has(record.id)) {
		return buildAuthoringEnvelopeSchema(record.payload_schema);
	}
	return record.payload_schema;
}

export interface LearnWriterRecord {
	id: string;
	definition_version: string;
	capability_id: string;
	native_path: 'learn';
	lane: LearnCapabilityRecord['kind'];
	purpose: string;
	modes: AuthoringMode[];
	instructions: AuthoringInstructions;
	schema_ref: string;
	payload_schema_ref: string;
	payload_schema: JsonSchema;
	/** Runtime interaction config schema (unchanged); present for envelope interactions. */
	config_schema?: JsonSchema;
	field_guidance: Record<string, string>;
	required_inputs: string[];
	requires: string[];
	capacity: Record<string, number>;
	negative_cases: string[];
	examples: unknown[];
	validator_refs: string[];
	converter_ref?: string;
	postprocessor_ref?: string;
	knowledge: KnowledgePolicySpec;
	assessment?: AssessmentPolicySpec;
	definition_hash: string;
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

function stableStringify(value: unknown): string {
	if (Array.isArray(value)) {
		return `[${value.map(stableStringify).join(',')}]`;
	}
	if (value && typeof value === 'object') {
		return `{${Object.entries(value as Record<string, unknown>)
			.filter(([, child]) => child !== undefined)
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([key, child]) => `${JSON.stringify(key)}:${stableStringify(child)}`)
			.join(',')}}`;
	}
	return JSON.stringify(value);
}

function hashDefinition(payload: Record<string, unknown>): string {
	return createHash('sha256').update(stableStringify(payload)).digest('hex');
}

function instructionResourceRef(record: LearnCapabilityRecord): string {
	const id = LEARN_INSTRUCTION_RESOURCE_IDS.has(record.id)
		? record.id
		: record.kind === 'content'
			? 'generic-content'
			: 'generic-interaction';
	return `contracts/authoring/instructions/${id}-writer-v1.txt`;
}

function readPackageResource(resourceRef: string): string {
	const url = new URL(`../../../../${resourceRef}`, import.meta.url);
	try {
		return readFileSync(fileURLToPath(url), 'utf8').trim();
	} catch (error) {
		throw new Error(`authoring instruction resource missing: ${resourceRef}`, {
			cause: error
		});
	}
}

function instructionsFor(record: LearnCapabilityRecord): AuthoringInstructions {
	if (isSelectable(record) && !LEARN_INSTRUCTION_RESOURCE_IDS.has(record.id)) {
		throw new Error(`no authoring instruction resource registered for learn/${record.id}`);
	}
	const resource_ref = instructionResourceRef(record);
	return { resource_ref, text: readPackageResource(resource_ref) };
}

function modesFor(record: LearnCapabilityRecord): AuthoringMode[] {
	if (record.kind === 'interaction') return ['generate', 'convert-approved'];
	return ['generate'];
}

function requiredInputsFor(record: LearnCapabilityRecord): string[] {
	const base = [
		'teaching_plan_block',
		'learn_selection_decision',
		'lesson_context',
		'allowed_facts',
		'terminology'
	];
	if (record.kind === 'interaction') {
		return [...base, 'learner_action', 'approved_items_when_converting'];
	}
	return base;
}

function evaluatorName(contractRef: string | null): string | null {
	if (!contractRef) return null;
	return contractRef.split('#')[1] ?? null;
}

function validatorRefsFor(record: LearnCapabilityRecord): string[] {
	const refs = ['learn.payload_schema'];
	const evaluator = evaluatorName(record.evaluation.contract_ref);
	if (evaluator) refs.push(`learn.${evaluator}`);
	for (const ref of refs) {
		if (!REGISTERED_VALIDATOR_REFS.has(ref)) {
			throw new Error(`unknown validator_ref "${ref}" for learn/${record.id}`);
		}
	}
	return refs;
}

function knowledgeFor(record: LearnCapabilityRecord): KnowledgePolicySpec {
	return {
		default: 'supplied_preferred',
		supported: ['supplied_only', 'supplied_preferred', 'objective_development']
	};
}

function assessmentFor(record: LearnCapabilityRecord): AssessmentPolicySpec | undefined {
	if (record.kind !== 'interaction') return undefined;
	if (record.id === 'short-response') {
		return {
			default: 'automatic_preferred',
			supported: ['automatic_required', 'automatic_preferred', 'teacher_review'],
			teacher_review_permitted: true
		};
	}
	if (CORE_INTERACTION_ENVELOPE_IDS.has(record.id)) {
		return {
			default: 'automatic_required',
			supported: ['automatic_required'],
			teacher_review_permitted: false
		};
	}
	return undefined;
}

function converterRefFor(record: LearnCapabilityRecord): string | undefined {
	const evaluator = evaluatorName(record.evaluation.contract_ref);
	if (evaluator === 'quizContentToInteractionContract') return 'learn.quizContentToInteractionContract';
	if (evaluator === 'fillBlankContentToInteractionContract') {
		return 'learn.fillBlankContentToInteractionContract';
	}
	return record.kind === 'interaction' ? `learn.${record.id}.approved_item_converter` : undefined;
}

export function buildWriterView(records: LearnCapabilityRecord[]): LearnWriterView {
	const capabilities: Record<string, LearnWriterRecord> = {};
	for (const record of records) {
		const instructions = instructionsFor(record);
		const validator_refs = validatorRefsFor(record);
		const modes = modesFor(record);
		const required_inputs = requiredInputsFor(record);
		const converter_ref = converterRefFor(record);
		const usesEnvelope =
			record.kind === 'interaction' && CORE_INTERACTION_ENVELOPE_IDS.has(record.id);
		const configSchema = record.payload_schema;
		const payloadSchema = writerPayloadSchema(record);
		const fieldGuidance = usesEnvelope
			? envelopeFieldGuidance(record, record.field_guidance)
			: { ...record.field_guidance };
		const knowledge = knowledgeFor(record);
		const assessment = assessmentFor(record);
		const definitionPayload = {
			definition_version: AUTHORING_DEFINITION_VERSION,
			capability_id: record.id,
			native_path: 'learn',
			lane: record.kind,
			purpose: record.purpose,
			modes,
			instructions,
			schema_ref: record.payload_schema_ref,
			payload_schema: payloadSchema,
			...(usesEnvelope ? { config_schema: configSchema } : {}),
			field_guidance: fieldGuidance,
			required_inputs,
			requires: [...record.requires],
			capacity: { ...record.capacity },
			negative_cases: [...record.negative_cases],
			examples: record.examples,
			validator_refs,
			converter_ref,
			knowledge,
			...(assessment ? { assessment } : {}),
			asset_requirements: record.asset_requirements,
			evaluation: record.evaluation,
			allowed_config: record.allowed_config,
			default_behaviour: record.default_behaviour
		};
		capabilities[record.id] = {
			id: record.id,
			definition_version: AUTHORING_DEFINITION_VERSION,
			capability_id: record.id,
			native_path: 'learn',
			lane: record.kind,
			purpose: record.purpose,
			modes,
			instructions,
			schema_ref: record.payload_schema_ref,
			payload_schema_ref: record.payload_schema_ref,
			payload_schema: payloadSchema,
			...(usesEnvelope ? { config_schema: configSchema } : {}),
			field_guidance: fieldGuidance,
			required_inputs,
			requires: [...record.requires],
			capacity: { ...record.capacity },
			negative_cases: [...record.negative_cases],
			examples: record.examples,
			validator_refs,
			...(converter_ref ? { converter_ref } : {}),
			knowledge,
			...(assessment ? { assessment } : {}),
			definition_hash: hashDefinition(definitionPayload),
			asset_requirements: record.asset_requirements,
			source_refs: [
				record.readiness_evidence.source_path,
				instructions.resource_ref,
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
