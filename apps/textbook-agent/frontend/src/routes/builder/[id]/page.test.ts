// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '$lib/api/errors';

const { pageState, goto, logout, loadBuilderLessonWithFallback } = vi.hoisted(() => ({
	pageState: {
		params: { id: 'lesson-123' },
		url: new URL('http://localhost/builder/lesson-123')
	},
	goto: vi.fn(),
	logout: vi.fn(),
	loadBuilderLessonWithFallback: vi.fn()
}));

vi.mock('$app/environment', () => ({
	browser: true
}));

vi.mock('$app/state', () => ({
	page: pageState
}));

vi.mock('$app/navigation', () => ({
	goto
}));

vi.mock('$lib/shared/stores/auth', () => ({
	logout
}));

vi.mock('$lib/learn/authoring/builder/persistence/server-sync', () => ({
	loadBuilderLessonWithFallback
}));

vi.mock('$lib/learn/document/DocumentEditor.svelte', async () => ({
	default: (await import('./__fixtures__/MockDocumentEditor.svelte')).default
}));

import BuilderLessonPage from './+page.svelte';

function learnDoc(title = 'Fractions basics') {
	return {
		version: 2,
		id: 'lesson-123',
		title,
		subject: 'mathematics',
		nodes: [{ id: 'n1', kind: 'paragraph', text: 'Hello' }],
		created_at: '2026-01-01T00:00:00.000Z',
		updated_at: '2026-01-01T00:00:00.000Z'
	};
}

describe('builder lesson route', () => {
	beforeEach(() => {
		goto.mockReset();
		logout.mockReset();
		loadBuilderLessonWithFallback.mockReset();
	});

	afterEach(() => {
		cleanup();
	});

	it('loads LearnDocument v2 into the editor', async () => {
		loadBuilderLessonWithFallback.mockResolvedValue({
			document: learnDoc(),
			source: 'server'
		});
		render(BuilderLessonPage);
		await waitFor(() => {
			expect(screen.getByText('LearnDocument v2 editor')).toBeTruthy();
			expect(screen.getByTestId('mock-document-editor')).toBeTruthy();
		});
	});

	it('shows retired message for LessonDocument v1', async () => {
		loadBuilderLessonWithFallback.mockResolvedValue({
			document: {
				version: 1,
				id: 'lesson-123',
				title: 'Old',
				subject: 'math',
				sections: [],
				blocks: {},
				media: {}
			},
			source: 'server'
		});
		render(BuilderLessonPage);
		await waitFor(() => {
			expect(screen.getByText('Legacy lesson retired')).toBeTruthy();
		});
	});

	it('logs out on 401', async () => {
		loadBuilderLessonWithFallback.mockRejectedValue(new ApiError(401, 'Unauthorized', 'auth'));
		render(BuilderLessonPage);
		await waitFor(() => {
			expect(logout).toHaveBeenCalled();
			expect(goto).toHaveBeenCalledWith('/login', { replaceState: true });
		});
	});
});
