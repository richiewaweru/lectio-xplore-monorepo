/**
 * `@lectio/contracts` — the neutral instructional vocabulary shared by the Print
 * and Learn native paths.
 *
 * This package owns no renderers, no payload schemas and no native inventory. It
 * has no Svelte, Python or renderer dependency so a planner, a backend exporter
 * or a test fixture can all depend on the same vocabulary.
 */

export type { InstructionalIntentId, InstructionalIntentRecord } from './intents';
export {
	INSTRUCTIONAL_INTENT_IDS,
	INSTRUCTIONAL_INTENT_SOURCE,
	INSTRUCTIONAL_VOCABULARY_VERSION,
	getInstructionalIntent,
	instructionalIntentRecords,
	isInstructionalIntentId,
	isTeachingSelectableIntent,
	listIntentBoundaries,
	listTeachingSelectableIntentIds
} from './intents';

export type { LearnerActionId, LearnerActionRecord } from './actions';
export {
	LEARNER_ACTION_IDS,
	LEARNER_ACTION_VOCABULARY_VERSION,
	getLearnerAction,
	isLearnerActionId,
	learnerActionRecords,
	listPassiveActionIds,
	listResponseActionIds,
	listSpatialActionIds
} from './actions';

export type { TeachingView, TeachingViewAction, TeachingViewIntent } from './teaching-view';
export { TEACHING_VIEW_VERSION, buildTeachingView } from './teaching-view';

export {
	LEARN_COMPONENT_ID_SAMPLE,
	LEARN_INTERACTION_KIND_IDS,
	NATIVE_DETAIL_KEYS,
	PRINT_OBJECT_IDS,
	SHARED_WITH_NATIVE_BY_DESIGN,
	identifierShapedNativeIds,
	nativeInventoryIds
} from './native-inventory';
