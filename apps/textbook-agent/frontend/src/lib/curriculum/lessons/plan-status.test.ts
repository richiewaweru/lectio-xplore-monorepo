import { describe, expect, it } from 'vitest';

import {
	canRegeneratePlan,
	canRetryPlan,
	isPlanPollingState,
	planFailureMessage,
	planPhaseFromPreparation,
	planProgressText
} from './plan-status';
import type { PreparationProgress, PreparationWorkspaceStatus } from '$lib/types/units';

const progress = (over: Partial<PreparationProgress> = {}): PreparationProgress => ({
	items_total: 5,
	items_ready: 0,
	items_failed: 0,
	teaching_plan: 'not_started',
	failed_work_item_ids: [],
	...over
});

describe('planPhaseFromPreparation', () => {
	it('maps every canonical preparation state to a page phase', () => {
		const phase = (s: PreparationWorkspaceStatus['state'], kind?: 'structural' | 'teaching_plan') =>
			planPhaseFromPreparation({ state: s, review_kind: kind ?? null });
		expect(phase('not_started')).toBe('idle');
		expect(phase('planning')).toBe('working');
		expect(phase('awaiting_review', 'structural')).toBe('structural');
		expect(phase('awaiting_review', 'teaching_plan')).toBe('teaching');
		expect(phase('approved')).toBe('approved');
		expect(phase('failed_recoverable')).toBe('failed_recoverable');
		expect(phase('failed_terminal')).toBe('failed_terminal');
		expect(phase('legacy_unsupported')).toBe('legacy_unsupported');
		expect(planPhaseFromPreparation(null)).toBe('idle');
	});

	it('polls only while planning', () => {
		expect(isPlanPollingState('planning')).toBe(true);
		for (const s of [
			'not_started',
			'awaiting_review',
			'approved',
			'failed_recoverable',
			'failed_terminal',
			'legacy_unsupported'
		] as const) {
			expect(isPlanPollingState(s)).toBe(false);
		}
	});
});

describe('planProgressText', () => {
	it('reports practice item progress, then the teaching plan', () => {
		expect(planProgressText(progress({ items_ready: 3 }))).toBe('Writing practice items: 3/5 cards');
		expect(planProgressText(progress({ items_ready: 5, teaching_plan: 'queued' }))).toBe(
			'Writing the Teaching Plan…'
		);
		expect(planProgressText(progress({ items_ready: 5, teaching_plan: 'running' }))).toBe(
			'Writing the Teaching Plan…'
		);
	});

	it('falls back to a generic line without progress', () => {
		expect(planProgressText(null)).toMatch(/preparing/i);
		expect(planProgressText(progress({ items_total: 0 }))).toMatch(/preparing/i);
	});
});

describe('planFailureMessage and actions', () => {
	it('shows the legacy re-prepare copy', () => {
		expect(planFailureMessage({ state: 'legacy_unsupported' })).toBe(
			'Prepared before the planning update — re-prepare this lesson.'
		);
	});

	it('describes recoverable failures with the failed card count', () => {
		const msg = planFailureMessage({
			state: 'failed_recoverable',
			progress: progress({ items_failed: 2 })
		});
		expect(msg).toMatch(/2 practice items could not be written/);
	});

	it('uses the backend message for terminal failures', () => {
		expect(
			planFailureMessage({ state: 'failed_terminal', error: { message: 'Invalid plan' } })
		).toBe('Invalid plan');
		expect(planFailureMessage({ state: 'failed_terminal' })).toMatch(/regenerate/i);
	});

	it('allows retry only for retryable recoverable failures with failed items', () => {
		const base = {
			state: 'failed_recoverable' as const,
			retryable: true,
			run_id: 'run-1',
			progress: progress({ items_failed: 1, failed_work_item_ids: ['wi-1'] })
		};
		expect(canRetryPlan(base)).toBe(true);
		expect(canRetryPlan({ ...base, retryable: false })).toBe(false);
		expect(canRetryPlan({ ...base, run_id: null })).toBe(false);
		expect(canRetryPlan({ ...base, progress: progress() })).toBe(false);
		expect(canRetryPlan({ ...base, state: 'failed_terminal' })).toBe(false);
	});

	it('offers regenerate for failed runs only', () => {
		expect(canRegeneratePlan({ state: 'failed_terminal', run_id: 'r' })).toBe(true);
		expect(canRegeneratePlan({ state: 'failed_recoverable', run_id: 'r' })).toBe(true);
		expect(canRegeneratePlan({ state: 'failed_terminal', run_id: null })).toBe(false);
		expect(canRegeneratePlan({ state: 'planning', run_id: 'r' })).toBe(false);
		expect(canRegeneratePlan({ state: 'legacy_unsupported', run_id: null })).toBe(false);
	});
});
