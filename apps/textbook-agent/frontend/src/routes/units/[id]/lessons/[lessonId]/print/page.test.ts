// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	apiFetch: vi.fn(), downloadV3GenerationPdf: vi.fn(), getLessonIssues: vi.fn(),
	retryLessonRealization: vi.fn(), generatePrintRealization: vi.fn()
}));

vi.mock('$lib/api/client', () => ({ apiFetch: mocks.apiFetch }));
vi.mock('$lib/api/v3', () => ({ downloadV3GenerationPdf: mocks.downloadV3GenerationPdf }));
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
	});
	afterEach(cleanup);

	it('keeps a ready realization ready when its document preview fetch fails', async () => {
		render(PrintPage, { context: new Map([['lessonWorkspace', context()]]) });
		expect(await screen.findByText(/Print document unavailable/)).toBeTruthy();
		expect(screen.queryByRole('button', { name: /Retry preview|Retry Print/ })).toBeNull();
		expect(mocks.retryLessonRealization).not.toHaveBeenCalled();
		expect(screen.getByRole('link', { name: 'Edit' }).getAttribute('href')).toContain('/studio/print/print-o');
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
