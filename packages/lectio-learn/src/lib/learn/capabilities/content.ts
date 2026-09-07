/**
 * Content capability records, projected from the component registry.
 *
 * Section components already carry authored metadata, a Zod schema, field
 * contracts and an export policy. Re-typing all of that as a second hand-written
 * catalogue would guarantee the two drift, so these records are *generated* from
 * the modules and the export policy instead. Readiness therefore cannot be
 * claimed in the catalogue while the export policy says otherwise.
 */

import { lectioContentModules } from '$lib/lectio/registry/components';
import { isContentContractEligible } from '$lib/lectio/export-policy';
import type { LectioContentModule } from '$lib/lectio/core/types';
import {
	fillBlankContentToInteractionContract,
	quizContentToInteractionContract
} from '$lib/learn/interaction-contract';
import type { TeachingIntent } from '$lib/schema/component-meta';
import type { InstructionalIntentId, LearnerActionId } from '@lectio/contracts';
import { RESPONSE_SCHEMAS } from './schemas';
import type {
	CapabilityAvailability,
	CapabilityReadiness,
	LearnCapabilityRecord
} from './types';

const CONTRACT_VERSION = '1.0.0';

/**
 * Components a teacher attaches by hand in the Builder. They are real
 * capabilities, but a generation run must not select them, so they are
 * `manual-only` rather than absent.
 */
const MANUAL_ONLY_IDS = new Set(['image-block', 'video-embed']);

/**
 * Content components whose learner response is scored by a shared evaluator,
 * via the adapter named beside them. Anything not listed here does not collect
 * an auto-scored response, so it declares no response schema.
 */
const SHARED_EVALUATOR_BY_COMPONENT: Record<string, { kind: string; adapter: string }> = {
	'quiz-check': {
		kind: 'choice',
		adapter: 'interaction-contract.ts#quizContentToInteractionContract'
	},
	'fill-in-blank': {
		kind: 'fill-blank',
		adapter: 'interaction-contract.ts#fillBlankContentToInteractionContract'
	}
};

/** Fail fast if an adapter named above is removed or renamed. */
const ADAPTERS = [quizContentToInteractionContract, fillBlankContentToInteractionContract];
if (ADAPTERS.some((adapter) => typeof adapter !== 'function')) {
	throw new Error('a shared evaluator adapter named in the capability catalogue is missing');
}

/** Neutral learner actions per web interaction hint. */
const ACTION_BY_INTERACTION: Record<string, LearnerActionId[]> = {
	none: ['read-explanation'],
	reveal: ['read-explanation'],
	input: ['enter-text'],
	choice: ['select-one'],
	manipulation: ['order-items'],
	'media-control': ['read-explanation']
};

/**
 * Canonical instructional intents per authored `teachingIntent`.
 *
 * `teachingIntent` is Learn's own nine-value palette vocabulary and is coarser
 * than the 32-intent canonical catalogue, so this is a widening map, not a
 * rename: one palette value admits several canonical intents. Every value on the
 * right is checked against `@lectio/contracts` by `capabilities/content.test.ts`,
 * so a typo cannot quietly invent an intent.
 */
const INTENTS_BY_TEACHING_INTENT: Record<TeachingIntent, InstructionalIntentId[]> = {
	explain: ['explain', 'explain-cause', 'interpret'],
	define: ['define', 'name-parts'],
	'show-how': ['demonstrate', 'model-thinking', 'practise-guided'],
	practice: ['practise-guided', 'practise-independent', 'check-understanding'],
	reflect: ['reflect', 'evaluate'],
	warn: ['warn', 'diagnose-misconception'],
	visualize: ['show-structure', 'trace-flow', 'compare'],
	structure: ['orient', 'state-goal', 'summarise'],
	engage: ['orient', 'activate-prior-knowledge']
};

function readiness(module: LectioContentModule): {
	readiness: CapabilityReadiness;
	availability: CapabilityAvailability;
	blocking_reasons: string[];
	path_to_readiness: string[];
} {
	const id = module.metadata.id;
	if (MANUAL_ONLY_IDS.has(id)) {
		return {
			readiness: 'manual-only',
			availability: 'available',
			blocking_reasons: [
				'Excluded from the generation-facing content contract: it carries teacher-attached media, not generated section content.'
			],
			path_to_readiness: [
				'None planned. This capability is deliberately teacher-authored; it is available in the Builder and must stay out of generation selection.'
			]
		};
	}
	if (!isContentContractEligible(module)) {
		return {
			readiness: 'planned',
			availability: 'unavailable',
			blocking_reasons: [
				'Excluded from the content contract by export policy, so no consumer can select it.',
				module.metadata.sectionField === null
					? 'No section field: the component is inline-only and has no place in the section content model.'
					: 'Listed in CONTENT_CONTRACT_EXCLUDED_COMPONENT_IDS.'
			],
			path_to_readiness: [
				'Give the component a section field and remove it from the export-policy exclusion list.',
				'Add a content contract declaring the format of every authored field.'
			]
		};
	}
	if (module.metadata.status === 'planned') {
		return {
			readiness: 'planned',
			availability: 'unavailable',
			blocking_reasons: ['Component status is `planned`: the implementation is not finished.'],
			path_to_readiness: ['Finish the implementation and move status to `beta`, then `stable`.']
		};
	}
	if (module.metadata.status === 'beta') {
		return {
			readiness: 'planned',
			availability: 'incomplete',
			blocking_reasons: [
				'Component status is `beta`: it is exported and selectable, but not yet proven stable enough to promote.'
			],
			path_to_readiness: [
				'Prove the component end to end in a live run, then promote status to `stable`.'
			]
		};
	}
	if (!module.contentContract) {
		return {
			readiness: 'planned',
			availability: 'incomplete',
			blocking_reasons: [
				'No content contract: exported field cards are empty, so a writer has no per-field format guidance.'
			],
			path_to_readiness: ['Add a content-contract.ts declaring every authored field.']
		};
	}
	return {
		readiness: 'generation-ready',
		availability: 'available',
		blocking_reasons: [],
		path_to_readiness: []
	};
}

function projectContentCapability(module: LectioContentModule): LearnCapabilityRecord {
	const meta = module.metadata;
	const state = readiness(module);
	const interaction = module.web?.interaction ?? 'none';
	const evaluationMode = module.web?.responseEvaluation ?? 'none';
	const fieldContracts = module.contentContract?.fieldContracts ?? {};
	const shared = SHARED_EVALUATOR_BY_COMPONENT[meta.id];
	// A component may only claim auto-scoring when a shared evaluator actually
	// backs it. `responseEvaluation: 'auto-score'` on its own is an intention.
	const autoScored = evaluationMode === 'auto-score' && shared !== undefined;

	return {
		id: meta.id,
		native_path: 'learn',
		kind: 'content',
		contract_version: CONTRACT_VERSION,
		purpose: meta.role,
		cognitive_job: meta.cognitiveJob,
		supported_intents: [...INTENTS_BY_TEACHING_INTENT[meta.teachingIntent]],
		supported_actions: ACTION_BY_INTERACTION[interaction] ?? ['read-explanation'],
		choose_when: meta.generationHint ?? meta.role,
		reject_when:
			state.availability === 'available'
				? `Reject when the section does not need to ${meta.cognitiveJob.toLowerCase()}, or when the payload would exceed the declared capacity.`
				: state.blocking_reasons[0] ?? 'Not selectable in its current state.',
		prerequisites:
			meta.sectionField === null
				? ['Hosted inside another block; it has no section field of its own.']
				: [`The lesson section carries a \`${meta.sectionField}\` payload.`],
		requires: module.contentContract?.componentConstraints ?? [],
		capacity: Object.fromEntries(
			Object.entries(meta.capacity)
				.filter((entry): entry is [string, number] => typeof entry[1] === 'number')
		),
		payload_schema_ref:
			meta.sectionField === null
				? `learn/content/${meta.id}/inline.v1`
				: `section-content-schema.json#/properties/${meta.sectionField}`,
		// The authored schema is a Zod type, not JSON Schema. The exporter resolves
		// the real subschema from the generated SectionContent schema; the record
		// keeps the reference so the identity is never guessed.
		payload_schema: {},
		field_guidance: Object.fromEntries(
			Object.entries(fieldContracts).map(([field, contract]) => [
				field,
				`${contract.description} Format: ${contract.format}.${
					contract.renderBehavior ? ` ${contract.renderBehavior}` : ''
				}`
			])
		),
		examples: module.examples,
		negative_cases: [],
		renderer_ref: `packages/lectio-learn/src/lib/lectio/components/${meta.id}/Component.svelte`,
		response_schema: shared ? (RESPONSE_SCHEMAS[shared.kind] ?? null) : null,
		evaluation: {
			mode: autoScored
				? 'auto-score'
				: evaluationMode === 'teacher-review' || evaluationMode === 'rubric'
					? 'teacher-review'
					: 'none',
			contract_ref: shared
				? `packages/lectio-learn/src/lib/learn/${shared.adapter}`
				: null,
			partial_scoring: autoScored && shared?.kind === 'fill-blank',
			invalid_response_policy: autoScored ? 'reject' : 'not-applicable'
		},
		allowed_config: {},
		default_behaviour: {
			behaviour_modes: [...meta.behaviourModes],
			narration: module.web?.narration ?? 'none',
			learner_band: module.web?.learnerBand ?? 'core'
		},
		asset_requirements: meta.capabilities.isMedia
			? {
					kinds: ['image', 'svg', 'video'],
					identity: 'An existing asset id; media components never describe an unproduced asset.',
					coordinate_system: null,
					authoring_tool: 'Builder media attachment'
				}
			: null,
		accessibility: {
			keyboard_operable: !meta.capabilities.interactive || interaction !== 'manipulation',
			narration: module.web?.narration ?? 'none',
			notes: module.web?.accessibilityNotes ?? 'No component-specific note authored.'
		},
		presentation_variants: [...meta.behaviourModes],
		readiness: state.readiness,
		availability: state.availability,
		readiness_evidence: {
			source_path: `packages/lectio-learn/src/lib/lectio/components/${meta.id}`,
			data_schema: true,
			evaluator: autoScored,
			authoring_support: meta.sectionField !== null,
			renderer: true,
			keyboard_operable: !meta.capabilities.interactive || interaction !== 'manipulation',
			contract_export: isContentContractEligible(module),
			consumer_selection_support: isContentContractEligible(module),
			evidence:
				'Projected from the component module and export policy; asserted by capabilities/content.test.ts.'
		},
		blocking_reasons: state.blocking_reasons,
		path_to_readiness: state.path_to_readiness,
		compatibility: { since: '0.7.0', deprecates: [], migration: null }
	};
}

export const contentCapabilities: LearnCapabilityRecord[] = lectioContentModules.map((module) =>
	projectContentCapability(module)
);
