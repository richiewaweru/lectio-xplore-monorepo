/**
 * The Learn capability catalogue.
 *
 * One record per native implementation, plus generated views. The catalogue is
 * the only place readiness is declared, and `validateCapabilityRecords` refuses
 * a record whose declared readiness disagrees with its own evidence row.
 */

import { isInstructionalIntentId, isLearnerActionId } from '@lectio/contracts';
import { contentCapabilities } from './content';
import { interactionCapabilities } from './interactions';
import type { LearnCapabilityRecord } from './types';

export const CAPABILITY_CATALOGUE_VERSION = '1.0.0';

export const learnCapabilities: LearnCapabilityRecord[] = [
	...interactionCapabilities,
	...contentCapabilities
];

export function capabilityById(id: string): LearnCapabilityRecord | undefined {
	return learnCapabilities.find((record) => record.id === id);
}

/**
 * Structural and honesty checks on the catalogue.
 *
 * The honesty checks matter more than the structural ones: a record may not
 * claim `generation-ready` unless every evidence flag that readiness implies is
 * true, and a record that is not `available` must say what blocks it and how to
 * unblock it. A blank field is not success.
 */
export function validateCapabilityRecords(
	records: readonly LearnCapabilityRecord[] = learnCapabilities
): string[] {
	const errors: string[] = [];
	const seen = new Set<string>();

	for (const record of records) {
		const where = `${record.native_path}/${record.id}`;
		if (seen.has(record.id)) errors.push(`${where}: duplicate capability id`);
		seen.add(record.id);

		if (!record.purpose) errors.push(`${where}: purpose is required`);
		if (!record.cognitive_job) errors.push(`${where}: cognitive_job is required`);
		if (!record.choose_when) errors.push(`${where}: choose_when is required`);
		if (!record.reject_when) errors.push(`${where}: reject_when is required`);
		if (!record.payload_schema_ref) errors.push(`${where}: payload_schema_ref is required`);
		if (!record.renderer_ref) errors.push(`${where}: renderer_ref is required`);

		// A capability describes itself in shared vocabulary or not at all: an
		// intent or action Print has never heard of cannot carry a shared plan.
		if (record.supported_intents.length === 0) {
			errors.push(`${where}: no supported_intents`);
		}
		for (const intent of record.supported_intents) {
			if (!isInstructionalIntentId(intent)) {
				errors.push(`${where}: "${intent}" is not a canonical instructional intent`);
			}
		}
		for (const action of record.supported_actions) {
			if (!isLearnerActionId(action)) {
				errors.push(`${where}: "${action}" is not a canonical learner action`);
			}
		}

		const evidence = record.readiness_evidence;
		if (record.readiness === 'generation-ready') {
			const required: Array<[keyof typeof evidence, string]> = [
				['data_schema', 'a payload schema'],
				['renderer', 'a renderer'],
				['contract_export', 'a contract export'],
				['consumer_selection_support', 'consumer selection support']
			];
			for (const [flag, label] of required) {
				if (evidence[flag] !== true) {
					errors.push(`${where}: claims generation-ready without ${label}`);
				}
			}
			if (record.availability !== 'available') {
				errors.push(
					`${where}: generation-ready but availability is "${record.availability}"; readiness and availability must agree`
				);
			}
		}

		if (record.availability !== 'available' && record.blocking_reasons.length === 0) {
			errors.push(`${where}: availability "${record.availability}" with no blocking_reasons`);
		}
		if (record.availability !== 'available' && record.path_to_readiness.length === 0) {
			errors.push(`${where}: availability "${record.availability}" with no path_to_readiness`);
		}
		if (record.availability === 'available' && record.readiness === 'generation-ready') {
			if (record.blocking_reasons.length > 0) {
				errors.push(`${where}: selectable but still lists blocking_reasons`);
			}
		}

		if (record.evaluation.mode === 'auto-score' && !record.evaluation.contract_ref) {
			errors.push(`${where}: auto-score without an evaluator contract_ref`);
		}
		if (record.evaluation.mode === 'auto-score' && record.response_schema === null) {
			errors.push(`${where}: auto-score without a response schema`);
		}
		if (record.evaluation.mode === 'none' && record.evaluation.partial_scoring) {
			errors.push(`${where}: partial_scoring with no evaluation`);
		}
		if (record.asset_requirements && record.asset_requirements.kinds.length === 0) {
			errors.push(`${where}: asset_requirements with no asset kinds`);
		}
	}

	return errors;
}

export { contentCapabilities, interactionCapabilities };
export * from './types';

/**
 * The evaluator surface is re-exported here so a Node consumer needs exactly
 * one renderer-free entry point to select a capability *and* score a response.
 * Without this, selecting from `@lectio/learn/capabilities` but evaluating from
 * the root entry would drag Svelte components into a server or a script.
 */
export type {
	AttemptPolicy,
	BlankAnswer,
	CompletionRule,
	EvaluationOutcome,
	EvaluationResult,
	FeedbackSpec,
	InteractionAttemptState,
	InteractionKindId,
	LearnInteractionContract,
	ShortResponseConfig,
	ShortResponseEvaluationMode
} from '$lib/learn/interaction-contract';
export {
	InteractionConfigError,
	InteractionResponseError,
	createAttemptState,
	evaluateInteraction,
	fillBlankContentToInteractionContract,
	isComplete,
	parseInteractionContract,
	quizContentToInteractionContract,
	recordAttempt,
	serializeInteractionContract,
	shortResponseToInteractionContract,
	validateInteractionContract
} from '$lib/learn/interaction-contract';
export {
	CONFIG_SCHEMAS as CAPABILITY_CONFIG_SCHEMAS,
	RESPONSE_SCHEMAS as CAPABILITY_RESPONSE_SCHEMAS
} from './schemas';
export {
	buildRuntimeView,
	buildSelectionView,
	buildTeachingView,
	buildWriterView,
	isSelectable,
	RUNTIME_VIEW_VERSION,
	SELECTION_VIEW_VERSION,
	TEACHING_VIEW_VERSION,
	WRITER_VIEW_VERSION,
	type LearnRuntimeRecord,
	type LearnRuntimeView,
	type LearnSelectionRecord,
	type LearnSelectionView,
	type LearnTeachingCoverage,
	type LearnTeachingView,
	type LearnWriterRecord,
	type LearnWriterView
} from './views';
