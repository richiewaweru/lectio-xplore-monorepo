// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	apiFetch: vi.fn(), downloadGenerationPdf: vi.fn(), getLessonIssues: vi.fn(),
	retryLessonRealization: vi.fn(), generatePrintRealization: vi.fn(), goto: vi.fn()
}));
const pageState = vi.hoisted(() => ({ url: new URL('http://localhost/units/unit-1/lessons/lesson-1/print') }));

vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$app/state', () => ({ page: pageState }));

vi.mock('$lib/api/client', () => ({ apiFetch: mocks.apiFetch }));
vi.mock('$lib/api/realizations', () => ({ downloadGenerationPdf: mocks.downloadGenerationPdf }));
vi.mock('$lib/api/units', () => ({ getLessonIssues: mocks.getLessonIssues, retryLessonRealization: mocks.retryLessonRealization, generatePrintRealization: mocks.generatePrintRealization }));
vi.mock('$lib/print/components/studio/LectioPageDocumentView.svelte', async () => ({ default: (await import('../../../../../studio/__fixtures__/MockGeneric.svelte')).default }));

import PrintPage from './+page.svelte';

function context(): any {
	return {
		unitId: 'unit-1', lessonId: 'lesson-1', unit: null, path: { status: 'approved' },
		lesson: { title: 'Plant water', objective: 'Explain water movement' }, statusFresh: true, statusError: null,
		preparation: {
			path_lesson_id: 'lesson-1', lesson_revision: 1, generation_id: 'debug-prep', generation_status: 'failed', workflow_stage: 'failed_terminal',
			objective_hash: 'hash', stale: false, can_prepare: false, can_regenerate: false,
			workspace: {
				preparation: { state: 'approved', approved_snapshot_verified: true },
				learn: { state: 'not_created' },
				print: { state: 'ready', realization_id: 'print-r', output_id: 'print-o', open_href: '/studio/print/print-o' }
			}
		},
		refreshPreparation: vi.fn(async () => {})
	};
}

describe('Unit Print workspace document and realization errors', () => {
	beforeEach(() => {
		for (const mock of Object.values(mocks)) mock.mockReset();
		mocks.getLessonIssues.mockResolvedValue({ issues: [] });
		mocks.apiFetch.mockResolvedValue({ ok: false, status: 503 });
		pageState.url = new URL('http://localhost/units/unit-1/lessons/lesson-1/print');
	});
	afterEach(cleanup);

	it('keeps a ready realization ready when its document preview fetch fails', async () => {
		render(PrintPage, { context: new Map([['lessonWorkspace', context()]]) });
		expect(await screen.findByText(/Print document unavailable/)).toBeTruthy();
		expect(screen.queryByRole('button', { name: /Retry preview|Retry Print/ })).toBeNull();
		expect(mocks.retryLessonRealization).not.toHaveBeenCalled();
		expect(screen.getByRole('tab', { name: 'Edit' }).getAttribute('href')).toContain('/studio/print/print-o');
	});

	it('shows Edit as a disabled tab with a reason until a Print output exists', async () => {
		const notCreated = context();
		notCreated.preparation.workspace.print = { state: 'not_created' };
		render(PrintPage, { context: new Map([['lessonWorkspace', notCreated]]) });
		const edit = await screen.findByRole('tab', { name: 'Edit' });
		expect(edit.getAttribute('aria-disabled')).toBe('true');
		expect(edit.getAttribute('title')).toBe('Available once the lesson is ready');
		expect(edit.getAttribute('href')).toBeNull();
		await fireEvent.click(edit);
		expect(mocks.goto).not.toHaveBeenCalled();
	});

	it('moves to the Issues tab through the URL and renders it from ?tab=issues', async () => {
		mocks.getLessonIssues.mockResolvedValue({
			issues: [{ id: 'page-gap', path: 'print', severity: 'error', category: 'document', code: 'PAGE_GAP', message: 'Worksheet page is missing', details: '', repairable: false, source: 'workspace', group: 'blocking' }]
		});
		render(PrintPage, { context: new Map([['lessonWorkspace', context()]]) });
		await fireEvent.click(await screen.findByRole('tab', { name: 'Issues' }));
		expect(mocks.goto).toHaveBeenCalledWith('/units/unit-1/lessons/lesson-1/print?tab=issues', { replaceState: true, noScroll: true, keepFocus: true });

		cleanup();
		mocks.goto.mockReset();
		pageState.url = new URL('http://localhost/units/unit-1/lessons/lesson-1/print?tab=issues');
		render(PrintPage, { context: new Map([['lessonWorkspace', context()]]) });
		expect(await screen.findByText('Worksheet page is missing')).toBeTruthy();
		expect(screen.getByRole('tab', { name: 'Issues' }).getAttribute('aria-selected')).toBe('true');
	});

	it('keeps queued Print guidance on refresh and does not offer retry', async () => {
		const queued = context();
		queued.preparation.workspace.print.state = 'queued';
		render(PrintPage, { context: new Map([['lessonWorkspace', queued]]) });
		expect(await screen.findByText(/Refresh to check progress/)).toBeTruthy();
		expect(screen.queryByRole('button', { name: /Retry Print/ })).toBeNull();
		expect(mocks.retryLessonRealization).not.toHaveBeenCalled();
	});

	it('shows a typed recoverable Print failure and only then offers Retry', async () => {
		const failed = context();
		failed.preparation.workspace.print = {
			state: 'failed_recoverable',
			realization_id: 'print-failed',
			output_id: 'print-output-failed',
			open_href: '/studio/print/print-output-failed',
			error: {
				code: 'TIMEOUT', error_type: 'provider', failure_class: 'timeout',
				message: 'Print export timed out.', retryable: true, stage: 'exporting', attempt: 1
			}
		};
		render(PrintPage, { context: new Map([['lessonWorkspace', failed]]) });
		expect(await screen.findByText(/Print export timed out/)).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Retry Print' })).toBeTruthy();
	});
});
