import {
	INSTRUCTIONAL_VOCABULARY_VERSION,
	instructionalIntentRecords,
	type InstructionalIntentRecord
} from './intents';
import {
	LEARNER_ACTION_VOCABULARY_VERSION,
	learnerActionRecords,
	type LearnerActionRecord
} from './actions';

export const TEACHING_VIEW_VERSION = '1.0.0';

export interface TeachingViewIntent {
	id: string;
	label: string;
	pedagogical_role: string;
	cognitive_job: string;
	choose_when: string | null;
	/** Neighbouring intents that win instead, so the planner can tell them apart. */
	boundaries: Array<{ intent: string; when: string }>;
}

export interface TeachingViewAction {
	id: string;
	label: string;
	learner_does: string;
	requires_response: boolean;
}

/**
 * Generated teaching view: the only vocabulary a shared teaching plan may use.
 *
 * Deliberately absent: page object ids, Learn component or interaction ids,
 * payload schemas, capacity/layout limits and payload examples. A teaching plan
 * that cannot name native inventory cannot pre-commit either native path.
 */
export interface TeachingView {
	view: 'teaching';
	view_version: string;
	intent_vocabulary_version: string;
	action_vocabulary_version: string;
	intents: TeachingViewIntent[];
	learner_actions: TeachingViewAction[];
}

export interface TeachingViewSource {
	intents: Record<string, InstructionalIntentRecord>;
	actions: Record<string, LearnerActionRecord>;
	intent_vocabulary_version: string;
	action_vocabulary_version: string;
}

/**
 * Pure projection from vocabulary records to the teaching view.
 *
 * Kept independent of the committed data files so the exporter and the
 * regeneration gate can both drive it from an arbitrary source revision.
 */
export function projectTeachingView(source: TeachingViewSource): TeachingView {
	const intents: TeachingViewIntent[] = Object.entries(source.intents)
		.filter(([, record]) => record.teaching_selectable === true)
		.map(([id, record]) => ({
			id,
			label: record.label,
			pedagogical_role: record.pedagogical_role,
			cognitive_job: record.cognitive_job,
			choose_when: record.choose_when ?? null,
			boundaries: Object.entries(record.boundaries ?? {})
				.filter((entry): entry is [string, string] => typeof entry[1] === 'string')
				.map(([intent, when]) => ({ intent, when }))
		}));

	const learner_actions: TeachingViewAction[] = Object.entries(source.actions).map(
		([id, record]) => ({
			id,
			label: record.label,
			learner_does: record.learner_does,
			requires_response: record.requires_response
		})
	);

	return {
		view: 'teaching',
		view_version: TEACHING_VIEW_VERSION,
		intent_vocabulary_version: source.intent_vocabulary_version,
		action_vocabulary_version: source.action_vocabulary_version,
		intents,
		learner_actions
	};
}

/** The teaching view for the vocabulary revision committed to this package. */
export function buildTeachingView(): TeachingView {
	return projectTeachingView({
		intents: instructionalIntentRecords,
		actions: learnerActionRecords,
		intent_vocabulary_version: INSTRUCTIONAL_VOCABULARY_VERSION,
		action_vocabulary_version: LEARNER_ACTION_VOCABULARY_VERSION
	});
}
