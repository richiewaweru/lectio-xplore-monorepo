import type { V3ChunkedPlanStage, V3ChunkedStatus } from '$lib/types/v3';

export type PlanGenerationPhase =
	| 'working'
	| 'structural'
	| 'teaching'
	| 'approved'
	| 'failed_recoverable'
	| 'failed_terminal';

// writing_sections/writing_blocks are retired (P12B): no worker transitions
// into them any more, so a row still parked there can never advance. Treating
// them as active would make the UI poll forever; the backend's
// native_status.LEGACY_STATUSES projection reports next_action: "inspect_error"
// for these instead, which isPlanGenerationFailure-adjacent call sites should
// surface via planFailureMessage/error_detail rather than a spinner.
const ACTIVE_STAGES = new Set<V3ChunkedPlanStage>([
	'queued',
	'planning_forms',
	'assembling',
	'stage1_running',
	'stage2_running',
	'variants_running',
	'blueprint_ready'
]);

export function isPlanGenerationActive(status: Pick<V3ChunkedStatus, 'stage'>): boolean {
	return ACTIVE_STAGES.has(status.stage);
}

// Retired pre-P11B stages (P12B): a row still parked here cannot ever resume,
// so it is reported as a non-retryable failure rather than an active stage.
const LEGACY_STALLED_STAGES = new Set<V3ChunkedPlanStage>(['writing_sections', 'writing_blocks']);

export function isPlanGenerationFailure(
	status: Pick<V3ChunkedStatus, 'stage'>
): status is Pick<V3ChunkedStatus, 'stage'> & {
	stage: 'stage1_failed' | 'failed_recoverable' | 'failed_terminal' | 'writing_sections' | 'writing_blocks';
} {
	return (
		status.stage === 'stage1_failed' ||
		status.stage === 'failed_recoverable' ||
		status.stage === 'failed_terminal' ||
		LEGACY_STALLED_STAGES.has(status.stage)
	);
}

export function planFailureMessage(status: Pick<V3ChunkedStatus, 'stage' | 'error' | 'error_detail'>): string {
	const detail = status.error_detail;
	const message =
		typeof detail?.message === 'string'
			? detail.message
			: typeof status.error === 'string'
				? status.error
				: '';

		if (LEGACY_STALLED_STAGES.has(status.stage)) {
			return 'This generation is parked at a pre-P11B execution stage that no longer runs. It cannot resume automatically and needs attention.';
		}
		if (status.stage === 'failed_terminal' || status.stage === 'stage1_failed') {
			return 'Lesson preparation could not be completed. Lectio needs attention before this lesson can continue.';
		}
		if (message.toLowerCase().includes('teaching')) {
			return 'Lesson preparation failed while generating the teaching plan. Lectio exhausted its automatic repairs.';
		}
		return 'Lesson preparation failed. Lectio exhausted its automatic repairs and is ready for a retry.';
}

export function failureAllowsRetry(
	status: Pick<V3ChunkedStatus, 'stage' | 'next_action' | 'error_detail'>
): boolean {
	if (status.stage !== 'failed_recoverable') return false;
	if (status.next_action && status.next_action.startsWith('retry_')) return true;
	return status.error_detail?.retryable === true;
}
