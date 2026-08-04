export function friendlyGenerationErrorMessage(
	error: string | null,
	type: string | null,
	code: string | null = null
): string {
	if (code === 'stale_generation') {
		return error ?? 'This generation was interrupted before it finished. Please try again.';
	}
	if (code === 'generation_timeout') {
		return error ?? 'This generation took too long to finish and was stopped. Please try again.';
	}
	if (code === 'orphaned_generation') {
		return error ?? 'This generation lost track of its runtime state and was stopped safely. Please try again.';
	}
	if (type === 'provider_error') {
		return error ?? 'The AI provider rejected the request. Check your provider configuration and try again.';
	}
	if (type === 'pipeline_error') {
		return 'The generation pipeline encountered an error. Please try again with different input.';
	}
	return error ?? 'Generation failed unexpectedly.';
}
