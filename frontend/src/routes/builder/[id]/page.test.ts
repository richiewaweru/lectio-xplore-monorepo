// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '$lib/api/errors';

const { pageState, goto, logout, loadBuilderLessonWithFallback, fetchV3Document, getChunkedPlan, getChunkedPlanStatus, v3PackToBuilderDocument, partitionGenerationIssues } = vi.hoisted(() => ({
	pageState: {
		params: { id: 'lesson-123' },
		url: new URL('http://localhost/builder/lesson-123')
	},
	goto: vi.fn(),
	logout: vi.fn(),
	loadBuilderLessonWithFallback: vi.fn(),
	fetchV3Document: vi.fn(),
	getChunkedPlan: vi.fn(),
	getChunkedPlanStatus: vi.fn(),
	v3PackToBuilderDocument: vi.fn(),
	partitionGenerationIssues: vi.fn()
}));

const mockStore = {
	document: null as Record<string, unknown> | null,
	selectedSectionId: null as string | null,
	selectedBlockId: null as string | null,
	editingBlockId: null as string | null,
	orderedSections: [] as Array<{ id: string; title: string }>,
	saveStatus: 'saved' as 'saved' | 'saving' | 'error',
	loadDocument(doc: Record<string, unknown>) {
		this.document = doc;
	},
	undo: vi.fn(),
	redo: vi.fn(),
	flushSave: vi.fn(),
	stopEditing: vi.fn(),
	deselectBlock: vi.fn(),
	startEditing: vi.fn(),
	duplicateBlock: vi.fn(),
	getSectionIdForBlock: vi.fn(() => null),
	removeBlock: vi.fn(),
	selectBlock: vi.fn(),
	insertSectionsFromGeneration: vi.fn(),
	refreshGenerationIssues: vi.fn()
};

vi.mock('$app/environment', () => ({
	browser: true
}));

vi.mock('$app/state', () => ({
	page: pageState
}));

vi.mock('$app/navigation', () => ({
	goto
}));

vi.mock('$lib/stores/auth', () => ({
	logout
}));

vi.mock('$lib/builder/persistence/server-sync', () => ({
	loadBuilderLessonWithFallback
}));

vi.mock('$lib/builder/stores/document.svelte', () => ({
	createDocumentStore: () => mockStore
}));

vi.mock('$lib/api/v3', () => ({ fetchV3Document, getChunkedPlan, getChunkedPlanStatus }));

vi.mock('$lib/builder/adapters/from-generation', () => ({
	v3PackToBuilderDocument,
	partitionGenerationIssues
}));

vi.mock('$lib/builder/components/shell/AppShell.svelte', async () => ({
	default: (await import('./__fixtures__/MockAppShell.svelte')).default
}));

import BuilderLessonPage from './+page.svelte';

function lesson(title = 'Fractions basics') {
	return {
		id: 'lesson-123',
		title,
		subject: 'mathematics',
		preset_id: 'blue-classroom',
		sections: [],
		blocks: {},
		media: {}
	};
}

describe('builder lesson route', () => {
	beforeEach(() => {
		mockStore.document = null;
		mockStore.selectedSectionId = null;
		mockStore.selectedBlockId = null;
		mockStore.editingBlockId = null;
		mockStore.orderedSections = [];
		mockStore.saveStatus = 'saved';
		loadBuilderLessonWithFallback.mockReset();
		goto.mockReset();
		logout.mockReset();
		pageState.params.id = 'lesson-123';
		pageState.url = new URL('http://localhost/builder/lesson-123');
		fetchV3Document.mockReset();
		getChunkedPlan.mockReset();
		getChunkedPlanStatus.mockReset();
		getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'default-generation', stage: 'stage2_running', doc_version: 'snapshot-v1',
			failed_sections: [], blueprint_id: null, execution_started: true, next_action: 'wait_for_stage2'
		});
		v3PackToBuilderDocument.mockReset();
		partitionGenerationIssues.mockReset();
		partitionGenerationIssues.mockReturnValue({ sectionIssues: {}, documentLevelIssues: [] });
		mockStore.insertSectionsFromGeneration.mockReset();
		mockStore.refreshGenerationIssues.mockReset();
		localStorage.clear();
	});

	afterEach(() => {
		cleanup();
	});

	it('renders builder shell when lesson loads', async () => {
		loadBuilderLessonWithFallback.mockResolvedValueOnce({
			document: lesson('Algebra review'),
			source: 'server'
		});

		render(BuilderLessonPage);

		await waitFor(() => expect(loadBuilderLessonWithFallback).toHaveBeenCalledWith('lesson-123'));
		expect((await screen.findByTestId('mock-app-shell')).textContent ?? '').toContain('Algebra review');
	});

	it('shows not found state on 404', async () => {
		loadBuilderLessonWithFallback.mockRejectedValueOnce(new ApiError(404, 'Lesson not found'));

		render(BuilderLessonPage);

		expect(await screen.findByText('Lesson not found')).toBeTruthy();
		expect(screen.getByRole('link', { name: /back to builder lessons/i }).getAttribute('href')).toBe(
			'/builder'
		);
	});

	it('redirects to login on unauthorized response', async () => {
		loadBuilderLessonWithFallback.mockRejectedValueOnce(new ApiError(401, 'Unauthorized'));

		render(BuilderLessonPage);

		await waitFor(() => expect(logout).toHaveBeenCalledTimes(1));
		await waitFor(() => expect(goto).toHaveBeenCalledWith('/login', { replaceState: true }));
	});

	it('rehydrates pending plan, inserts a snapshot, and stops polling at terminal status', async () => {
		const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
		const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-1');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({ document: lesson(), source: 'server' });
		getChunkedPlan.mockResolvedValueOnce({
			structural_plan: {
				lesson_mode: 'first_exposure', lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'all' }, question_plan: [],
				sections: [{ id: 's1', title: 'Introduction', role: 'intro', visual_required: false, transition_note: null, components: [] }]
			}
		});
		fetchV3Document.mockResolvedValueOnce({ status: 'final_ready', sections: [] });
		v3PackToBuilderDocument.mockReturnValueOnce(lesson());

		render(BuilderLessonPage);

		await waitFor(() => expect(fetchV3Document).toHaveBeenCalledWith('gen-1'));
		expect(getChunkedPlan).toHaveBeenCalledWith('gen-1');
		expect(mockStore.insertSectionsFromGeneration).toHaveBeenCalledWith(
			expect.any(Object),
			[{ id: 's1', title: 'Introduction', position: 0 }]
		);
		const pollTimerIndex = setIntervalSpy.mock.calls.findIndex(([, delay]) => delay === 4000);
		const pollTimer = setIntervalSpy.mock.results[pollTimerIndex]?.value;
		expect(pollTimerIndex).toBeGreaterThanOrEqual(0);
		await waitFor(() => expect(clearIntervalSpy).toHaveBeenCalledWith(pollTimer));
		expect(screen.queryByTestId('mock-pending-s1')).toBeNull();
		setIntervalSpy.mockRestore();
		clearIntervalSpy.mockRestore();
	});

	it('shows route-only pending skeletons while the document snapshot is not ready', async () => {
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-pending');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({ document: lesson(), source: 'server' });
		getChunkedPlan.mockResolvedValueOnce({
			structural_plan: {
				lesson_mode: 'first_exposure', lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'all' }, question_plan: [],
				sections: [{ id: 's2', title: 'Practice', role: 'practice', visual_required: false, transition_note: null, components: [] }]
			}
		});
		fetchV3Document.mockRejectedValueOnce(new Error('Document not ready'));

		render(BuilderLessonPage);

		expect(await screen.findByTestId('mock-pending-s2')).toBeTruthy();
		expect(mockStore.document?.sections).toEqual([]);
		expect(mockStore.insertSectionsFromGeneration).not.toHaveBeenCalled();
	});

	it('shows section progress and pending skeletons while generation is active', async () => {
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-progress');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({
			document: { ...lesson(), sections: [{ id: 's1', title: 'One', position: 0, block_ids: [] }] },
			source: 'server'
		});
		getChunkedPlan.mockResolvedValueOnce({
			structural_plan: {
				lesson_mode: 'first_exposure', lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'all' }, question_plan: [],
				sections: [
					{ id: 's1', title: 'One' }, { id: 's2', title: 'Two' }, { id: 's3', title: 'Three' }
				]
			}
		});
		fetchV3Document.mockResolvedValueOnce({
			status: 'streaming_preview', sections: [],
			progress: { stage: 'writing', sections: { s1: 'ready', s2: 'writing', s3: 'pending' } }
		});
		v3PackToBuilderDocument.mockReturnValueOnce(lesson());

		render(BuilderLessonPage);

		expect(await screen.findByText('1/3 sections ready')).toBeTruthy();
		expect(screen.getByTestId('mock-pending-s2')).toBeTruthy();
		expect(screen.getByTestId('mock-pending-s3')).toBeTruthy();
	});

	it('keeps polling when a streaming snapshot already contains every planned section', async () => {
		const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
		const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-streaming');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({
			document: { ...lesson(), sections: [{ id: 's1', title: 'Introduction', position: 0, block_ids: ['header-1'] }] },
			source: 'server'
		});
		getChunkedPlan.mockResolvedValueOnce({
			structural_plan: {
				lesson_mode: 'first_exposure', lesson_intent: { goal: 'Goal', structure_rationale: 'Why' },
				anchor: { example: 'Anchor', reuse_scope: 'all' }, question_plan: [],
				sections: [{ id: 's1', title: 'Introduction', role: 'intro', visual_required: false, transition_note: null, components: [] }]
			}
		});
		fetchV3Document.mockResolvedValueOnce({ status: 'streaming_preview', sections: [] });
		v3PackToBuilderDocument.mockReturnValueOnce(lesson());

		render(BuilderLessonPage);

		await waitFor(() => expect(fetchV3Document).toHaveBeenCalledWith('gen-streaming'));
		const pollTimerIndex = setIntervalSpy.mock.calls.findIndex(([, delay]) => delay === 4000);
		const pollTimer = setIntervalSpy.mock.results[pollTimerIndex]?.value;
		expect(pollTimerIndex).toBeGreaterThanOrEqual(0);
		expect(clearIntervalSpy).not.toHaveBeenCalledWith(pollTimer);
		setIntervalSpy.mockRestore();
		clearIntervalSpy.mockRestore();
	});

	it('fetches the document only when the snapshot version changes', async () => {
		const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-versioned');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({ document: lesson(), source: 'server' });
		getChunkedPlan.mockResolvedValue({ structural_plan: null });
		getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-versioned', stage: 'stage2_running', doc_version: 'doc-v1',
			failed_sections: [], blueprint_id: null, execution_started: true, next_action: 'wait_for_stage2'
		});
		fetchV3Document.mockResolvedValue({ status: 'streaming_preview', sections: [] });
		v3PackToBuilderDocument.mockReturnValue(lesson());

		render(BuilderLessonPage);
		await waitFor(() => expect(fetchV3Document).toHaveBeenCalledTimes(1));
		const pollCall = setIntervalSpy.mock.calls.find(([, delay]) => delay === 4000);
		const pollTick = pollCall?.[0] as (() => void) | undefined;
		expect(pollTick).toBeDefined();

		pollTick?.();
		await waitFor(() => expect(getChunkedPlanStatus).toHaveBeenCalledTimes(2));
		expect(fetchV3Document).toHaveBeenCalledTimes(1);

		getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-versioned', stage: 'stage2_running', doc_version: 'doc-v2',
			failed_sections: [], blueprint_id: null, execution_started: true, next_action: 'wait_for_stage2'
		});
		pollTick?.();
		await waitFor(() => expect(fetchV3Document).toHaveBeenCalledTimes(2));
		setIntervalSpy.mockRestore();
	});

	it('persists dismissal of document-level generation issues per lesson', async () => {
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-issues');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({ document: lesson(), source: 'server' });
		getChunkedPlan.mockResolvedValue({ structural_plan: null });
		fetchV3Document.mockResolvedValue({ status: 'streaming_preview', sections: [] });
		v3PackToBuilderDocument.mockReturnValue(lesson());
		partitionGenerationIssues.mockReturnValue({
			sectionIssues: {},
			documentLevelIssues: [
				{ id: 'anchor-1', severity: 'major', message: 'Anchor drifted.', kind: 'anchor_drift', resolved: false }
			]
		});

		render(BuilderLessonPage);
		await fireEvent.click(await screen.findByRole('button', { name: 'Dismiss lesson issue' }));

		expect(localStorage.getItem('lectio:dismissed-doc-issues:lesson-123')).toBe('["anchor-1"]');
		expect(screen.queryByText('Anchor drifted.')).toBeNull();
	});

	it('keeps polling quietly when a running generation has no document yet', async () => {
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-no-doc');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({ document: lesson(), source: 'server' });
		getChunkedPlan.mockResolvedValue({ structural_plan: null });
		fetchV3Document.mockRejectedValue(new ApiError(404, 'Document not found'));

		render(BuilderLessonPage);
		await waitFor(() => expect(fetchV3Document).toHaveBeenCalledTimes(1));

		expect(screen.queryByText(/generation update delayed/i)).toBeNull();
	});

	it('stops on blocked execution and links recovery to Studio', async () => {
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-blocked');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({ document: lesson(), source: 'server' });
		getChunkedPlan.mockResolvedValue({ structural_plan: null });
		getChunkedPlanStatus.mockResolvedValue({
			generation_id: 'gen-blocked', stage: 'assembly_blocked', doc_version: null,
			failed_sections: ['practice'], blueprint_id: null, execution_started: false,
			next_action: 'retry_failed_sections', error: 'Practice section failed.'
		});

		render(BuilderLessonPage);

		expect(await screen.findByText('Generation needs recovery')).toBeTruthy();
		expect(screen.getByText('Failed sections: practice')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Open recovery in Studio' }).getAttribute('href')).toBe(
			'/studio?generation_id=gen-blocked'
		);
		expect(fetchV3Document).not.toHaveBeenCalled();
	});

	it('shows the runtime outcome message for a terminal review-needed draft', async () => {
		pageState.url = new URL('http://localhost/builder/lesson-123?generation_id=gen-review');
		loadBuilderLessonWithFallback.mockResolvedValueOnce({ document: lesson(), source: 'server' });
		getChunkedPlan.mockResolvedValue({ structural_plan: null });
		fetchV3Document.mockResolvedValue({
			status: 'draft_needs_review', sections: [], progress: { stage: 'failed', sections: {} }
		});
		v3PackToBuilderDocument.mockReturnValue(lesson());

		render(BuilderLessonPage);

		expect(
			await screen.findByText('Draft rendered, but major issues remain after review/repair.')
		).toBeTruthy();
	});
});
