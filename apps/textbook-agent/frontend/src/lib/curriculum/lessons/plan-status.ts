/**
 * Plan-page status mapping. The only input is the lesson-status DTO's
 * `workspace.preparation` (Option D): the preparation Run is the job status.
 */
import type { PreparationProgress, PreparationWorkspaceStatus } from '$lib/types/units';

export type PlanPagePhase =
	| 'idle'
	| 'structural'
	| 'working'
	| 'teaching'
	| 'approved'
	| 'failed_recoverable'
	| 'failed_terminal'
	| 'legacy_unsupported';

export const LEGACY_UNSUPPORTED_COPY = 'Prepared before the planning update — re-prepare this lesson.';

/** Map the canonical preparation state to the page phase. */
export function planPhaseFromPreparation(
	prep: Pick<PreparationWorkspaceStatus, 'state' | 'review_kind'> | null | undefined
): PlanPagePhase {
	switch (prep?.state) {
		case undefined:
		case 'not_started':
			return 'idle';
		case 'planning':
			return 'working';
		case 'awaiting_review':
			return prep.review_kind === 'structural' ? 'structural' : 'teaching';
		case 'approved':
			return 'approved';
		case 'failed_recoverable':
			return 'failed_recoverable';
		case 'failed_terminal':
			return 'failed_terminal';
		case 'legacy_unsupported':
			return 'legacy_unsupported';
	}
}

/** Terminal for polling purposes: anything but `planning`. */
export function isPlanPollingState(state: PreparationWorkspaceStatus['state'] | undefined): boolean {
	return state === 'planning';
}

/** Teacher-facing progress line while a plan is being generated. */
export function planProgressText(progress: PreparationProgress | null | undefined): string {
	if (!progress) return 'Preparing structure and teaching plan…';
	const { items_total: total, items_ready: ready, teaching_plan: teaching } = progress;
	if (teaching === 'queued' || teaching === 'running') return 'Writing the Teaching Plan…';
	if (teaching === 'ready') return 'Finishing the Teaching Plan…';
	if (total > 0 && ready < total) return `Writing practice items: ${ready}/${total} cards`;
	if (total > 0) return 'Practice items ready. Preparing the Teaching Plan…';
	return 'Preparing structure and teaching plan…';
}

export function planFailureMessage(
	prep: Pick<PreparationWorkspaceStatus, 'state' | 'error' | 'progress'> | null | undefined
): string {
	if (prep?.state === 'legacy_unsupported') return LEGACY_UNSUPPORTED_COPY;
	const message = prep?.error?.message?.trim();
	if (prep?.state === 'failed_recoverable') {
		const failed = prep.progress?.items_failed ?? 0;
		const base =
			failed > 0
				? `${failed} practice ${failed === 1 ? 'item' : 'items'} could not be written.`
				: 'Plan generation stopped before it finished.';
		return message ? `${base} ${message}` : `${base} You can retry.`;
	}
	return message || 'Plan generation could not be completed. Regenerate the plan to try again.';
}

/** Retry needs a Run and at least one failed work item to reopen. */
export function canRetryPlan(
	prep: Pick<PreparationWorkspaceStatus, 'state' | 'retryable' | 'run_id' | 'progress'> | null | undefined
): boolean {
	return Boolean(
		prep?.state === 'failed_recoverable' &&
			prep.retryable === true &&
			prep.run_id &&
			(prep.progress?.failed_work_item_ids.length ?? 0) > 0
	);
}

/** Regenerate is offered for terminal failure or a non-retryable recoverable one. */
export function canRegeneratePlan(
	prep: Pick<PreparationWorkspaceStatus, 'state' | 'run_id'> | null | undefined
): boolean {
	return Boolean(
		prep &&
			prep.run_id &&
			(prep.state === 'failed_terminal' || prep.state === 'failed_recoverable')
	);
}
