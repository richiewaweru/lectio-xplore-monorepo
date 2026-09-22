import type { V3ChunkedPlanStage, V3ChunkedStatus } from '$lib/types/v3';

export type PlanGenerationPhase =
	| 'working'
	| 'structural'
	| 'teaching'
	| 'approved'
	| 'failed_recoverable'
	| 'failed_terminal';

const ACTIVE_STAGES = new Set<V3ChunkedPlanStage>([
	'queued',
	'planning_forms',
	'writing_sections',
	'writing_blocks',
	'assembling',
	'stage1_running',
	'stage2_running',
	'variants_running',
	'blueprint_ready'
]);

export function isPlanGenerationActive(status: Pick<V3ChunkedStatus, 'stage'>): boolean {
	return ACTIVE_STAGES.has(status.stage);
}

export function isPlanGenerationFailure(
	status: Pick<V3ChunkedStatus, 'stage'>
): status is Pick<V3ChunkedStatus, 'stage'> & {
	stage: 'stage1_failed' | 'failed_recoverable' | 'failed_terminal';
} {
	return (
		status.stage === 'stage1_failed' ||
		status.stage === 'failed_recoverable' ||
		status.stage === 'failed_terminal'
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
