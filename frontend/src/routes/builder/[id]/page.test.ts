// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '$lib/api/errors';

const { pageState, goto, logout, loadBuilderLessonWithFallback, fetchV3Document, getChunkedPlan, v3PackToBuilderDocument } = vi.hoisted(() => ({
	pageState: {
		params: { id: 'lesson-123' },
		url: new URL('http://localhost/builder/lesson-123')
	},
	goto: vi.fn(),
	logout: vi.fn(),
	loadBuilderLessonWithFallback: vi.fn(),
	fetchV3Document: vi.fn(),
	getChunkedPlan: vi.fn(),
	v3PackToBuilderDocument: vi.fn()
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
	insertSectionsFromGeneration: vi.fn()
};

vi.mock('$app/environment', () => ({
	browser: false
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

vi.mock('$lib/api/v3', () => ({ fetchV3Document, getChunkedPlan }));

vi.mock('$lib/builder/adapters/from-generation', () => ({ v3PackToBuilderDocument }));

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
		v3PackToBuilderDocument.mockReset();
		mockStore.insertSectionsFromGeneration.mockReset();
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
		await waitFor(() => expect(clearIntervalSpy).toHaveBeenCalled());
		expect(await screen.findByTestId('mock-pending-s1')).toBeTruthy();
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
});
