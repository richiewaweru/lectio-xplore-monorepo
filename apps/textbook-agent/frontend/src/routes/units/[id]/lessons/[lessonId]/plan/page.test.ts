// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	getPreparationStructure: vi.fn(),
	getLessonApproach: vi.fn(),
	approveLessonApproach: vi.fn(),
	startPreparationPlan: vi.fn(),
	regeneratePreparationPlan: vi.fn(),
	retryPreparationRun: vi.fn(),
	regeneratePathLesson: vi.fn(),
	rejectLessonApproach: vi.fn(),
	realizeLearnFromGeneration: vi.fn(),
	realizePrintFromGeneration: vi.fn(),
	getUnitGroups: vi.fn(),
	preparePathLesson: vi.fn(),
	generateLearnRealization: vi.fn(),
	generatePrintRealization: vi.fn(),
	retryLessonRealization: vi.fn(),
	getPreparedLessonStatus: vi.fn(),
	goto: vi.fn()
}));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/api/units', () => ({
	getUnitGroups: mocks.getUnitGroups,
	preparePathLesson: mocks.preparePathLesson,
	generateLearnRealization: mocks.generateLearnRealization,
	generatePrintRealization: mocks.generatePrintRealization,
	retryLessonRealization: mocks.retryLessonRealization,
	regeneratePathLesson: mocks.regeneratePathLesson,
	getPreparedLessonStatus: mocks.getPreparedLessonStatus
}));
vi.mock('$lib/api/lesson-planning', () => ({
	getPreparationStructure: mocks.getPreparationStructure,
	startPreparationPlan: mocks.startPreparationPlan,
	regeneratePreparationPlan: mocks.regeneratePreparationPlan,
	retryPreparationRun: mocks.retryPreparationRun
}));
vi.mock('$lib/api/teaching-plan', () => ({
	getLessonApproach: mocks.getLessonApproach,
	approveLessonApproach: mocks.approveLessonApproach,
	rejectLessonApproach: mocks.rejectLessonApproach
}));
vi.mock('$lib/api/realizations', () => ({
	realizeLearnFromGeneration: mocks.realizeLearnFromGeneration,
	realizePrintFromGeneration: mocks.realizePrintFromGeneration
}));
vi.mock('$lib/curriculum/lessons/StructuralPlanPreview.svelte', async () => ({
	default: (await import('../../../../../studio/__fixtures__/MockGeneric.svelte')).default
}));

import PlanPage from './+page.svelte';

const pending = {
	teaching_plan: {
		teaching_plan_id: 'tp-1', revision: 4, arc: 'Trace water through a plant.',
		sections: [{ slot_id: 'orient', blocks: [{ id: 'b1', intent: 'orient', brief: 'Observe a covered leaf.', evidence: 'A relevant observation.' }] }]
	},
	teaching_review: { status: 'pending', revision: 4 },
	teaching_plan_identity: { revision: 4, pending_content_hash: 'units-displayed-hash', pending_hash_verified: true }
};
const approved = {
	...pending,
	teaching_review: { status: 'approved', revision: 5, approved_revision: 4 },
	teaching_plan_identity: { revision: 5, approved_revision: 4, approved_content_hash: 'units-displayed-hash', approved_hash_verified: true }
};

function workspaceContext() {
	return {
		unitId: 'unit-1', lessonId: 'lesson-1', unit: null,
		path: { status: 'approved' },
		lesson: { title: 'Plant water', objective: 'Explain water movement' },
		preparation: {
			path_lesson_id: 'lesson-1', lesson_revision: 1, generation_id: 'generation-1',
			generation_status: 'awaiting_teaching_approval', workflow_stage: 'awaiting_teaching_approval',
			objective_hash: 'hash', stale: false, can_prepare: false, can_regenerate: false,
			workspace: {
				preparation: { state: 'awaiting_review', review_kind: 'teaching_plan', generation_id: 'generation-1' },
				learn: { state: 'not_created' }, print: { state: 'not_created' }
			}
		},
		statusFresh: true, statusError: null,
		refreshPreparation: vi.fn(async () => {}), setPreparation: vi.fn()
	};
}

describe('Units Teaching Plan review', () => {
	beforeEach(() => {
		for (const mock of Object.values(mocks)) mock.mockReset();
		mocks.getPreparationStructure.mockRejectedValue(new Error('structural details not needed'));
		mocks.getLessonApproach.mockImplementation(() =>
			Promise.resolve(mocks.approveLessonApproach.mock.calls.length ? approved : pending)
		);
		mocks.approveLessonApproach.mockResolvedValue({ status: 'teaching_approved' });
	});
	afterEach(cleanup);

	it('renders visible content and submits the exact pending hash before showing verified approval', async () => {
		const ctx = workspaceContext();
		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		expect(await screen.findByText('Trace water through a plant.')).toBeTruthy();
		const approve = await screen.findByRole('button', { name: 'Approve plan' });
		expect((approve as HTMLButtonElement).disabled).toBe(false);
		await fireEvent.click(approve);
		await waitFor(() => expect(mocks.approveLessonApproach).toHaveBeenCalledWith('generation-1', {
			expected_revision: 4,
			expected_content_hash: 'units-displayed-hash',
			teacher_note: 'Approved',
			path: 'learn'
		}));
		expect(await screen.findByText('Teaching plan approved')).toBeTruthy();
		expect(screen.getByText('Trace water through a plant.')).toBeTruthy();
	});

	it('keeps approval disabled when the loaded Teaching Plan is blank', async () => {
		mocks.getLessonApproach.mockResolvedValue({
			...pending,
			teaching_plan: { teaching_plan_id: 'tp-1', revision: 4, arc: ' ', sections: [] }
		});
		render(PlanPage, { context: new Map([['lessonWorkspace', workspaceContext()]]) });
		const approve = await screen.findByRole('button', { name: 'Approve plan' });
		expect((approve as HTMLButtonElement).disabled).toBe(true);
	});

	it('does not show approval when the server rejects a stale displayed content hash', async () => {
		mocks.approveLessonApproach.mockRejectedValue(
			new Error('APPROVED_CONTENT_HASH_MISMATCH: The displayed plan changed. Reload and review it again.')
		);
		render(PlanPage, { context: new Map([['lessonWorkspace', workspaceContext()]]) });
		await fireEvent.click(await screen.findByRole('button', { name: 'Approve plan' }));
		expect(await screen.findByText(/APPROVED_CONTENT_HASH_MISMATCH/)).toBeTruthy();
		expect(screen.queryByText('Teaching plan approved')).toBeNull();
		expect(screen.getByRole('button', { name: 'Approve plan' })).toBeTruthy();
	});

	function withPrep(prep: Record<string, unknown>) {
		const ctx = workspaceContext();
		ctx.preparation.workspace.preparation = {
			generation_id: 'generation-1', ...prep
		} as unknown as typeof ctx.preparation.workspace.preparation;
		ctx.preparation.workflow_stage = 'ready'; // stale worker stage must be ignored
		return ctx;
	}

	it('shows canonical recoverable failure and retries the failed run items', async () => {
		const ctx = withPrep({
			state: 'failed_recoverable', run_id: 'run-1', retryable: true, recovery_action: 'retry',
			error: { message: 'The preparation run failed.', retryable: true },
			progress: { items_total: 5, items_ready: 3, items_failed: 2, teaching_plan: 'not_started', failed_work_item_ids: ['wi-1', 'wi-2'] }
		});
		mocks.retryPreparationRun.mockResolvedValue(undefined);
		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		expect(await screen.findByText('Lesson preparation needs a retry')).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Approve plan' })).toBeNull();
		expect(mocks.getLessonApproach).not.toHaveBeenCalled();
		await fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
		await waitFor(() => expect(mocks.retryPreparationRun).toHaveBeenCalledWith('run-1', ['wi-1', 'wi-2']));
		expect(ctx.refreshPreparation).toHaveBeenCalled();
	});

	it('offers Regenerate plan for terminal failure and shows 409 messages', async () => {
		const ctx = withPrep({ state: 'failed_terminal', run_id: 'run-1', recovery_action: 'regenerate', error: { message: 'Bad plan' } });
		mocks.regeneratePreparationPlan.mockRejectedValue(new Error('This plan has used all its attempts.'));
		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
		await fireEvent.click(await screen.findByRole('button', { name: 'Regenerate plan' }));
		await waitFor(() => expect(mocks.regeneratePreparationPlan).toHaveBeenCalledWith('generation-1'));
		expect(await screen.findByText('This plan has used all its attempts.')).toBeTruthy();
	});

	it('shows the legacy message and re-prepares through the stage-1 regenerate API', async () => {
		const ctx = withPrep({ state: 'legacy_unsupported', recovery_action: 'regenerate' });
		mocks.regeneratePathLesson.mockResolvedValue({});
		mocks.getUnitGroups.mockResolvedValue({ groups: [] });
		mocks.getPreparedLessonStatus.mockResolvedValue(ctx.preparation);
		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		expect(await screen.findByText(/Prepared before the planning update/)).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Re-prepare lesson' }));
		await waitFor(() => expect(mocks.regeneratePathLesson).toHaveBeenCalledTimes(1));
		expect(mocks.regeneratePathLesson.mock.calls[0][0]).toBe('unit-1');
		expect(ctx.setPreparation).toHaveBeenCalled();
	});

	it('shows planning progress from the lesson-status DTO', async () => {
		const ctx = withPrep({
			state: 'planning', run_id: 'run-1',
			progress: { items_total: 5, items_ready: 3, items_failed: 0, teaching_plan: 'not_started', failed_work_item_ids: [] }
		});
		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		expect(await screen.findByText('Writing practice items: 3/5 cards')).toBeTruthy();
		expect(mocks.getLessonApproach).not.toHaveBeenCalled();
	});

	it('starts planning through the preparation plan endpoint from structural review', async () => {
		const ctx = withPrep({ state: 'awaiting_review', review_kind: 'structural' });
		mocks.getPreparationStructure.mockResolvedValue({ generation_id: 'generation-1', structural_plan: { lesson_title: 'Plant water' } });
		mocks.startPreparationPlan.mockResolvedValue({ generation_id: 'generation-1', run_id: 'run-1', status: 'queued', attempt: 1, created: true, recovery_action: null });
		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		await fireEvent.click(await screen.findByRole('button', { name: 'Review concepts' }));
		await waitFor(() => expect(mocks.startPreparationPlan).toHaveBeenCalledWith('generation-1', { display_title: 'Plant water' }));
		expect(ctx.refreshPreparation).toHaveBeenCalled();
	});
});
