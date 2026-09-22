import { describe, expect, it } from 'vitest';

import {
	failureAllowsRetry,
	isPlanGenerationActive,
	isPlanGenerationFailure,
	planFailureMessage
} from './plan-status';

describe('lesson plan status projection', () => {
	it('treats persisted failures as explicit non-running states', () => {
		const status = {
			stage: 'failed_recoverable' as const,
			next_action: 'retry_native',
			error: 'provider timeout',
			error_detail: { retryable: true }
		};

		expect(isPlanGenerationFailure(status)).toBe(true);
		expect(isPlanGenerationActive(status)).toBe(false);
		expect(failureAllowsRetry(status)).toBe(true);
		expect(planFailureMessage(status)).toMatch(/failed/i);
	});

	it('does not allow retry for terminal failures', () => {
		const status = {
			stage: 'failed_terminal' as const,
			next_action: 'inspect_error',
			error: 'invalid contract',
			error_detail: { retryable: false }
		};

		expect(isPlanGenerationFailure(status)).toBe(true);
		expect(isPlanGenerationActive(status)).toBe(false);
		expect(failureAllowsRetry(status)).toBe(false);
		expect(planFailureMessage(status)).toMatch(/terminal|attention/i);
	});

	it('keeps actual execution stages pollable', () => {
		expect(isPlanGenerationActive({ stage: 'planning_forms' })).toBe(true);
		expect(isPlanGenerationActive({ stage: 'writing_blocks' })).toBe(true);
		expect(isPlanGenerationActive({ stage: 'awaiting_teaching_approval' })).toBe(false);
	});
});
