import { describe, expect, it } from 'vitest';

import { friendlyGenerationErrorMessage } from './error-messages';

describe('friendlyGenerationErrorMessage', () => {
	it('uses the stale generation message when recovery marked the run interrupted', () => {
		expect(
			friendlyGenerationErrorMessage(
				null,
				'runtime_error',
				'stale_generation'
			)
		).toBe('This generation was interrupted before it finished. Please try again.');
	});

	it('uses the timeout message for timed out generations', () => {
		expect(
			friendlyGenerationErrorMessage(
				null,
				'runtime_error',
				'generation_timeout'
			)
		).toBe('This generation took too long to finish and was stopped. Please try again.');
	});

	it('uses the orphaned generation message for forced runtime cleanup', () => {
		expect(
			friendlyGenerationErrorMessage(
				null,
				'runtime_error',
				'orphaned_generation'
			)
		).toBe(
			'This generation lost track of its runtime state and was stopped safely. Please try again.'
		);
	});

	it('preserves actionable provider errors', () => {
		expect(
			friendlyGenerationErrorMessage(
				"Provider 'claude' request failed: Anthropic reports that the API credit balance is too low.",
				'provider_error'
			)
		).toContain('credit balance');
	});

	it('keeps generic pipeline errors generic', () => {
		expect(
			friendlyGenerationErrorMessage(
				"Pipeline node 'CurriculumPlannerNode' failed",
				'pipeline_error'
			)
		).toBe('The generation pipeline encountered an error. Please try again with different input.');
	});

	it('falls back to the backend message for unknown failures', () => {
		expect(
			friendlyGenerationErrorMessage(
				'Unexpected runtime failure',
				'runtime_error',
				'unknown_runtime'
			)
		).toBe('Unexpected runtime failure');
	});
});
