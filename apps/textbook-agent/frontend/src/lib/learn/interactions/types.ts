/**
 * Shared types for Learn interaction shells mounted from LearnDocument v2 nodes.
 * Attempts stay outside ordinary document content — callers persist via onSubmit.
 */

export type FeedbackSpec = {
	correct: string;
	incorrect: string;
	partial?: string;
	saved?: string;
};

export type InteractionRole = 'predict' | 'practice' | 'check';

/**
 * Per-item marks after a check.
 * match/classify: {left_id: bool}; choice: {option_id: bool}; multi-select: {option_id: bool}
 * (true = that option's selected state is right); sequence/fill-blank: bool[] by position.
 */
export type ItemResults = Record<string, boolean> | boolean[] | null;

/** A response body in the exact shape the server expects (and returns as a reveal). */
export type LearnerResponse = Record<string, unknown>;

export type ServerEvaluation = {
	outcome: string;
	feedback: string;
	score_earned?: number;
	score_possible?: number;
	item_results?: ItemResults;
	/** Attempts used including this one. */
	attempts_used?: number;
	/** Tries left; null = unlimited; 0 = locked. */
	attempts_left?: number | null;
	/** Correct answer in the learner response shape, once the rules allow showing it. */
	reveal?: LearnerResponse | null;
};

/** Saved state used to restore a question on resume. */
export type InteractionState = {
	evaluation: ServerEvaluation | null;
	response: LearnerResponse | null;
};

export type KindProgress = { done: number; total: number };

export type InteractionSubmitHandler = (
	response: Record<string, unknown>
) => Promise<ServerEvaluation>;

export type AttemptSubmitHandler = (args: {
	interactionId: string;
	sectionId?: string;
	response: Record<string, unknown>;
}) => Promise<ServerEvaluation>;
