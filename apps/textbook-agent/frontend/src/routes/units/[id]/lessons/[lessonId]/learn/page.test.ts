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

function status(state: 'not_started' | 'planning' | 'approved' = 'planning') {
	return {
		path_lesson_id: 'lesson-1', lesson_revision: 1, generation_id: 'debug-prep',
		generation_status: 'ready', workflow_stage: 'ready', objective_hash: 'hash', stale: false,
		can_prepare: false, can_regenerate: false,
		workspace: {
			preparation: { state, generation_id: 'prep-1', approved_snapshot_verified: state === 'approved' },
			learn: { state: 'not_created' }, print: { state: 'not_created' }
		}
	};
}

function context(state: 'not_started' | 'planning' | 'approved' = 'planning', statusFresh = true) {
	return {
		unitId: 'unit-1', lessonId: 'lesson-1', unit: null,
		path: { status: 'approved' }, lesson: { title: 'Plant water', objective: 'Explain water movement' },
		preparation: status(state), statusFresh, statusError: null,
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
});
