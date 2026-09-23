// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	getChunkedPlanStatus: vi.fn(),
	getChunkedPlan: vi.fn(),
	getLessonApproach: vi.fn(),
	approveLessonApproach: vi.fn(),
	approveChunkedPlan: vi.fn(),
	rejectLessonApproach: vi.fn(),
	regenerateChunkedPlan: vi.fn(),
	realizeLearnFromGeneration: vi.fn(),
	realizePrintFromGeneration: vi.fn(),
	retryNativeGeneration: vi.fn(),
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
	getPreparedLessonStatus: mocks.getPreparedLessonStatus
}));
vi.mock('$lib/api/v3', () => ({
	getChunkedPlan: mocks.getChunkedPlan,
	getChunkedPlanStatus: mocks.getChunkedPlanStatus,
	getLessonApproach: mocks.getLessonApproach,
	approveLessonApproach: mocks.approveLessonApproach,
	approveChunkedPlan: mocks.approveChunkedPlan,
	rejectLessonApproach: mocks.rejectLessonApproach,
	regenerateChunkedPlan: mocks.regenerateChunkedPlan,
	realizeLearnFromGeneration: mocks.realizeLearnFromGeneration,
	realizePrintFromGeneration: mocks.realizePrintFromGeneration,
	retryNativeGeneration: mocks.retryNativeGeneration
}));
vi.mock('$lib/print/components/studio/V3PlanPreview.svelte', async () => ({
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
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'generation-1', stage: 'awaiting_teaching_approval', failed_sections: [], next_action: 'review'
		});
		mocks.getChunkedPlan.mockRejectedValue(new Error('structural details not needed'));
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

	it('shows a verified current draft despite a stale downstream ready stage', async () => {
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'generation-1', stage: 'ready', failed_sections: [], next_action: 'done'
		});
		render(PlanPage, { context: new Map([['lessonWorkspace', workspaceContext()]]) });
		expect(await screen.findByText('Trace water through a plant.')).toBeTruthy();
		expect((await screen.findByRole('button', { name: 'Approve plan' }) as HTMLButtonElement).disabled).toBe(false);
	});

	it('shows canonical recoverable preparation failure despite a stale ready worker stage', async () => {
		const ctx = workspaceContext();
		ctx.preparation.workflow_stage = 'ready';
		ctx.preparation.workspace.preparation = {
			state: 'failed_recoverable', generation_id: 'generation-1',
			error: { message: 'The preparation run failed.', retryable: true }
		} as unknown as typeof ctx.preparation.workspace.preparation;
		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		expect(await screen.findByText('Lesson preparation needs a retry')).toBeTruthy();
		expect(screen.getByText('The preparation run failed.')).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Approve plan' })).toBeNull();
		expect(mocks.getLessonApproach).not.toHaveBeenCalled();
	});

	it('refreshes stale structural review into Teaching Plan review after an approval conflict', async () => {
		const ctx = workspaceContext();
		ctx.preparation.workspace.preparation = {
			state: 'awaiting_review', review_kind: 'structural', generation_id: 'generation-1'
		} as unknown as typeof ctx.preparation.workspace.preparation;
		mocks.getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'generation-1', stage: 'awaiting_teaching_approval', failed_sections: [], next_action: 'review'
		});
		mocks.getChunkedPlan.mockResolvedValue({
			generation_id: 'generation-1', structural_plan: { lesson_title: 'Plant water' }
		});
		mocks.approveChunkedPlan.mockRejectedValue(new Error('Generation is not awaiting explicit approval'));
		ctx.refreshPreparation = vi.fn(async () => {
			ctx.preparation.workspace.preparation = {
				state: 'awaiting_review', review_kind: 'teaching_plan', generation_id: 'generation-1'
			} as unknown as typeof ctx.preparation.workspace.preparation;
		});

		render(PlanPage, { context: new Map([['lessonWorkspace', ctx]]) });
		await fireEvent.click(await screen.findByRole('button', { name: 'Review concepts' }));

		expect(await screen.findByText('Trace water through a plant.')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Approve plan' })).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Review concepts' })).toBeNull();
		expect(screen.queryByRole('alert')).toBeNull();
		expect(ctx.refreshPreparation).toHaveBeenCalledTimes(1);
	});
});
