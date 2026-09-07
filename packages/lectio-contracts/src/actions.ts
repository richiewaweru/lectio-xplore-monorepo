import actionVocabulary from '../data/learner-actions.v1.json';

/**
 * Canonical learner-action identifier: what the learner is asked to DO.
 *
 * Actions are deliberately native-neutral. Print satisfies `order-items` with a
 * numbered paper task; Learn satisfies it with a reorderable list. Neither
 * native path may rename an action or invent one locally.
 */
export type LearnerActionId = keyof typeof actionVocabulary.actions;

export interface LearnerActionRecord {
	label: string;
	learner_does: string;
	/** False for passive content actions; such actions need no evaluator. */
	requires_response: boolean;
	/** Shape of the learner response in neutral terms — not a payload schema. */
	response_shape: string;
	cardinality: string;
	/** True when the action cannot be authored without asset coordinate tooling. */
	requires_spatial_authoring?: boolean;
	note?: string;
}

const actions = actionVocabulary.actions as unknown as Record<string, LearnerActionRecord>;

export const LEARNER_ACTION_VOCABULARY_VERSION = actionVocabulary.vocabulary_version;

export const LEARNER_ACTION_IDS = Object.keys(actions) as LearnerActionId[];

export function getLearnerAction(id: string): LearnerActionRecord | undefined {
	return actions[id];
}

export function isLearnerActionId(id: string): id is LearnerActionId {
	return Object.hasOwn(actions, id);
}

/** Actions that produce something a native path must evaluate or collect. */
export function listResponseActionIds(): LearnerActionId[] {
	return LEARNER_ACTION_IDS.filter((id) => actions[id]?.requires_response === true);
}

/** Actions satisfied by passive content — no learner response exists. */
export function listPassiveActionIds(): LearnerActionId[] {
	return LEARNER_ACTION_IDS.filter((id) => actions[id]?.requires_response === false);
}

/** Actions blocked until asset coordinate authoring exists. */
export function listSpatialActionIds(): LearnerActionId[] {
	return LEARNER_ACTION_IDS.filter((id) => actions[id]?.requires_spatial_authoring === true);
}

export { actions as learnerActionRecords };
