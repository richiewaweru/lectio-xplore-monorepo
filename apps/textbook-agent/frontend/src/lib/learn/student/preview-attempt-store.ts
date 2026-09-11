/**
 * Preview attempt isolation contract for LearnDocument v2 student shell.
 * Preview mode never posts learner attempts to production storage.
 */
export const PREVIEW_ATTEMPT_CONTRACT = {
	persists_production_attempts: false,
	mode: 'preview'
} as const;
