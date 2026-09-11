/**
 * Shared types for Learn interaction shells mounted from LearnDocument v2 nodes.
 * Attempts stay outside ordinary document content — callers persist via onSubmit.
 */

export type FeedbackSpec = {
	correct: string;
	incorrect: string;
	partial?: string;
};

export type ServerEvaluation = {
	outcome: string;
	feedback: string;
	score_earned?: number;
	score_possible?: number;
};

export type InteractionSubmitHandler = (
	response: Record<string, unknown>
) => Promise<ServerEvaluation>;

export type AttemptSubmitHandler = (args: {
	interactionId: string;
	sectionId?: string;
	response: Record<string, unknown>;
}) => Promise<ServerEvaluation>;
