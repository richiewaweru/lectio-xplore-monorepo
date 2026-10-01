// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	getBuilderLesson: vi.fn(), openNativeLearnBuilderLesson: vi.fn(),
	publishLearnRelease: vi.fn(), listLearnReleases: vi.fn(), apiFetch: vi.fn(),
	getLessonIssues: vi.fn(), retryLessonRealization: vi.fn(), generateLearnRealization: vi.fn()
}));

vi.mock('$lib/learn/authoring/builder/api/lesson-crud', () => ({ getBuilderLesson: mocks.getBuilderLesson, openNativeLearnBuilderLesson: mocks.openNativeLearnBuilderLesson }));
vi.mock('$lib/learn/student/api/releases', () => ({ publishLearnRelease: mocks.publishLearnRelease, listLearnReleases: mocks.listLearnReleases }));
vi.mock('$lib/api/client', () => ({ apiFetch: mocks.apiFetch }));
vi.mock('$lib/api/errors', () => ({ ensureOk: vi.fn() }));
vi.mock('$lib/api/units', () => ({ getLessonIssues: mocks.getLessonIssues, retryLessonRealization: mocks.retryLessonRealization, generateLearnRealization: mocks.generateLearnRealization }));
vi.mock('$lib/learn/student/StudentLessonShell.svelte', async () => ({ default: (await import('../../../../../studio/__fixtures__/MockGeneric.svelte')).default }));

import LearnPage from './+page.svelte';

function status(
	state: 'not_started' | 'planning' | 'approved' = 'planning',
	learn: Record<string, unknown> = { state: 'not_created' }
) {
	return {
		path_lesson_id: 'lesson-1', lesson_revision: 1, generation_id: 'debug-prep',
		generation_status: 'ready', workflow_stage: 'ready', objective_hash: 'hash', stale: false,
		can_prepare: false, can_regenerate: false,
		workspace: {
			preparation: { state, generation_id: 'prep-1', approved_snapshot_verified: state === 'approved' },
			learn, print: { state: 'not_created' }
		}
	};
}

function context(
	state: 'not_started' | 'planning' | 'approved' = 'planning',
	statusFresh = true,
	learn?: Record<string, unknown>
) {
	return {
		unitId: 'unit-1', lessonId: 'lesson-1', unit: null,
		path: { status: 'approved' }, lesson: { title: 'Plant water', objective: 'Explain water movement' },
		preparation: status(state, learn), statusFresh, statusError: null,
		refreshPreparation: vi.fn(async () => {}), setPreparation: vi.fn()
	};
}

describe('Unit Learn workspace canonical actions', () => {
	beforeEach(() => {
		for (const mock of Object.values(mocks)) mock.mockReset();
		mocks.getLessonIssues.mockResolvedValue({ issues: [] });
		mocks.listLearnReleases.mockResolvedValue([]);
	});
	afterEach(cleanup);

	it('does not offer Create while preparation is not approved despite a ready worker stage', async () => {
		render(LearnPage, { context: new Map([['lessonWorkspace', context('planning')]]) });
		const create = await screen.findByRole('button', { name: 'Create Learn' });
		expect((create as HTMLButtonElement).disabled).toBe(true);
		expect(mocks.generateLearnRealization).not.toHaveBeenCalled();
	});

	it('offers Create only after the canonical approved snapshot is verified', async () => {
		render(LearnPage, { context: new Map([['lessonWorkspace', context('approved')]]) });
		const create = await screen.findByRole('button', { name: 'Create Learn' });
		expect((create as HTMLButtonElement).disabled).toBe(false);
	});

	it('disables Create when the last approved status could not be refreshed', async () => {
		render(LearnPage, { context: new Map([['lessonWorkspace', context('approved', false)]]) });
		const create = await screen.findByRole('button', { name: 'Create Learn' });
		expect((create as HTMLButtonElement).disabled).toBe(true);
	});

	it('shows a review-needed state with no retry action when the backend reports needs_review', async () => {
		render(LearnPage, {
			context: new Map([['lessonWorkspace', context('approved', true, { state: 'needs_review', shared_document_state: 'needs_review' })]])
		});
		await screen.findByText('This lesson needs a teacher review before Learn can be built');
		expect(screen.queryByRole('button', { name: /retry/i })).toBeNull();
	});

	it('shows document-preparation progress while the shared document is pending', async () => {
		render(LearnPage, {
			context: new Map([['lessonWorkspace', context('approved', true, { state: 'running', realization_id: 'learn-r', shared_document_state: 'pending' })]])
		});
		await screen.findByText('Preparing the lesson document');
	});

	it('prompts to regenerate when a ready Learn artifact has a stale shared document', async () => {
		mocks.getBuilderLesson.mockResolvedValue({
			document: { version: 2, id: 'doc-1', title: 'Lesson', subject: 'science', source: 'native', nodes: [], created_at: '', updated_at: '' }
		});
		render(LearnPage, {
			context: new Map([
				[
					'lessonWorkspace',
					context('approved', true, {
						state: 'ready',
						realization_id: 'learn-r',
						output_id: 'learn-o',
						open_href: '/builder/learn-o',
						shared_document_state: 'stale'
					})
				]
			])
		});
		await screen.findByText(/has changed since this Learn lesson was built/);
	});
});
