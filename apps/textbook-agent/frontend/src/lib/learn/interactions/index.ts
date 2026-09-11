export type {
	AttemptSubmitHandler,
	FeedbackSpec,
	InteractionSubmitHandler,
	ServerEvaluation
} from './types';

export { normalizeFeedback } from './feedback';
export { default as InteractionShell } from './InteractionShell.svelte';
export {
	ChoiceInteraction,
	MultiSelectInteraction,
	FillBlankInteraction,
	ClassifyInteraction,
	MatchPairsInteraction,
	SequenceInteraction,
	NumericInteraction,
	ShortResponseInteraction
} from './shells';

/** Wave 7 migration: retained shells live under this package path. */
export const RETAINED_INTERACTION_SHELLS = [
	'choice',
	'multi-select',
	'fill-blank',
	'classify',
	'match-pairs',
	'sequence',
	'numeric',
	'short-response'
] as const;
