/**
 * Learn capability records.
 *
 * One authoring record per native implementation, per
 * `docs/unit-native-program/pack/contracts/01_CAPABILITY_CONTRACT.md`. Indices
 * and compatibility views are generated from these records — never maintained
 * by hand in both directions.
 */

export type JsonSchema = Record<string, unknown>;

export type CapabilityKind = 'content' | 'interaction';

/** Readiness vocabulary from the pack capability schema. */
export type CapabilityReadiness = 'planned' | 'manual-only' | 'generation-ready';

/**
 * Package readiness and consumer execution support are separate facts.
 *
 * - `available` — a consumer can select and run it today.
 * - `incomplete` — the implementation exists and is contract-exported, but a
 *   declared step to readiness is still outstanding.
 * - `unavailable` — a hard prerequisite is missing, so it must not be offered.
 */
export type CapabilityAvailability = 'available' | 'incomplete' | 'unavailable';

export interface CapabilityEvaluation {
	mode: 'none' | 'auto-score' | 'teacher-review';
	/** Identity of the evaluator that implements this declaration. */
	contract_ref: string | null;
	/** True only when the evaluator really awards partial credit. */
	partial_scoring: boolean;
	/** How a structurally invalid response is handled. */
	invalid_response_policy: 'reject' | 'not-applicable';
}

/**
 * One readiness row per capability. A blank field is not success — the row
 * states what exists and what does not, and the test suite asserts the row
 * agrees with the declared readiness.
 */
export interface CapabilityReadinessEvidence {
	source_path: string;
	data_schema: boolean;
	evaluator: boolean;
	authoring_support: boolean;
	renderer: boolean;
	keyboard_operable: boolean;
	contract_export: boolean;
	consumer_selection_support: boolean;
	evidence: string;
}

export interface CapabilityAssetRequirements {
	kinds: string[];
	identity: string;
	coordinate_system: string | null;
	authoring_tool: string | null;
}

export interface LearnCapabilityRecord {
	id: string;
	native_path: 'learn';
	kind: CapabilityKind;
	contract_version: string;

	purpose: string;
	cognitive_job: string;

	/** Canonical instructional intent ids from `@lectio/contracts`. */
	supported_intents: string[];
	/** Canonical learner action ids; empty for passive content. */
	supported_actions: string[];

	choose_when: string;
	reject_when: string;
	/** What must already be true of the lesson before this can be selected. */
	prerequisites: string[];
	/** Machine-checkable obligations on the payload. */
	requires: string[];
	/** Bounded capacity constraints. */
	capacity: Record<string, number>;

	/** Identity of the exact authored payload schema. */
	payload_schema_ref: string;
	payload_schema: JsonSchema;
	field_guidance: Record<string, string>;
	examples: unknown[];
	negative_cases: string[];

	renderer_ref: string;
	/** Learner response schema; null when nothing is collected. */
	response_schema: JsonSchema | null;
	evaluation: CapabilityEvaluation;

	/** Configuration a consumer may set, and what happens when it does not. */
	allowed_config: Record<string, string>;
	default_behaviour: Record<string, unknown>;

	asset_requirements: CapabilityAssetRequirements | null;
	accessibility: {
		keyboard_operable: boolean;
		narration: 'none' | 'optional' | 'recommended';
		notes: string;
	};

	/** Variants that render differently but evaluate identically. */
	presentation_variants: string[];

	readiness: CapabilityReadiness;
	availability: CapabilityAvailability;
	readiness_evidence: CapabilityReadinessEvidence;
	/** Non-empty whenever availability is not `available`. */
	blocking_reasons: string[];
	/** Ordered, concrete steps that would make this selectable. */
	path_to_readiness: string[];

	compatibility: {
		since: string;
		deprecates: string[];
		migration: string | null;
	};
}
