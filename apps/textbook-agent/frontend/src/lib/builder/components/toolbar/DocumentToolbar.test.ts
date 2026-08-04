// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonDocument } from 'lectio';

const {
	getStorageEstimate,
	downloadLessonDocument,
	printDocument,
	downloadBuilderLessonPdf,
	checkBuilderLessonPrint
} = vi.hoisted(() => ({
	getStorageEstimate: vi.fn(),
	downloadLessonDocument: vi.fn(),
	printDocument: vi.fn(),
	downloadBuilderLessonPdf: vi.fn(),
	checkBuilderLessonPrint: vi.fn()
}));

vi.mock('$lib/builder/utils/storage-estimate', () => ({
	getStorageEstimate
}));

vi.mock('$lib/builder/utils/file-io', () => ({
	downloadLessonDocument
}));

vi.mock('$lib/builder/utils/pdf-export', () => ({
	printDocument,
	downloadBuilderLessonPdf,
	checkBuilderLessonPrint
}));

import DocumentToolbar from './DocumentToolbar.svelte';

const DOCUMENT: LessonDocument = {
	version: 1,
	id: 'lesson-1',
	title: 'Fractions basics',
	subject: 'mathematics',
	preset_id: 'blue-classroom',
	source: 'manual',
	sections: [],
	blocks: {},
	media: {},
	created_at: '2026-05-13T00:00:00Z',
	updated_at: '2026-05-13T00:00:00Z'
};

describe('DocumentToolbar', () => {
	beforeEach(() => {
		getStorageEstimate.mockResolvedValue(null);
		downloadBuilderLessonPdf.mockResolvedValue({ filename: 'lesson.pdf', pageCount: '3' });
		checkBuilderLessonPrint.mockResolvedValue({
			page_count_estimate: 4,
			oversized_blocks: [{ block: 'practice-stack', height: 1200 }],
			images: { loaded: 3, failed: 1, timed_out: 0 },
			print_contract_coverage: { declared: 5, total: 5 },
			warnings: ['Block practice-stack is taller than one A4 page.', '1 images failed to load.']
		});
	});

	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it('toggles print preview from toolbar action', async () => {
		const onTogglePrintPreview = vi.fn();

		render(DocumentToolbar, {
			document: DOCUMENT,
			lessonId: 'lesson-1',
			onTogglePrintPreview
		});

		await fireEvent.click(screen.getByTestId('toolbar-print-preview'));

		expect(onTogglePrintPreview).toHaveBeenCalledTimes(1);
	});

	it('exports teacher and student PDFs via backend endpoint helper', async () => {
		render(DocumentToolbar, {
			document: DOCUMENT,
			lessonId: 'lesson-1'
		});

		await fireEvent.click(screen.getByTestId('toolbar-export-teacher-pdf'));
		await fireEvent.click(screen.getByTestId('toolbar-export-student-pdf'));

		await waitFor(() => {
			expect(downloadBuilderLessonPdf).toHaveBeenCalledWith('lesson-1', 'teacher');
			expect(downloadBuilderLessonPdf).toHaveBeenCalledWith('lesson-1', 'student');
		});
	});

	it('shows retry save control when save status is error', async () => {
		const onRetrySave = vi.fn();

		render(DocumentToolbar, {
			document: DOCUMENT,
			lessonId: 'lesson-1',
			saveStatus: 'error',
			onRetrySave
		});

		await fireEvent.click(screen.getByTestId('toolbar-retry-save'));
		expect(onRetrySave).toHaveBeenCalledTimes(1);
	});

	it('shows estimated A4 page count from document blocks', () => {
		render(DocumentToolbar, {
			document: {
				...DOCUMENT,
				blocks: {
					'block-1': {
						id: 'block-1',
						component_id: 'practice-stack',
						content: {},
						position: 0
					},
					'block-2': {
						id: 'block-2',
						component_id: 'diagram-series',
						content: {},
						position: 1
					},
					'block-3': {
						id: 'block-3',
						component_id: 'comparison-grid',
						content: {},
						position: 2
					}
				}
			},
			lessonId: 'lesson-1'
		});

		const pageCount = screen.getByTestId('toolbar-page-count');
		expect(pageCount.textContent?.trim()).toBe('~2 pages');
		expect(pageCount.getAttribute('title')).toBe('~2 A4 pages');
	});

	it('checks print layout and shows measured warnings', async () => {
		render(DocumentToolbar, {
			document: DOCUMENT,
			lessonId: 'lesson-1'
		});

		await fireEvent.click(screen.getByTestId('toolbar-print-check'));

		await waitFor(() => {
			expect(checkBuilderLessonPrint).toHaveBeenCalledWith('lesson-1', 'teacher');
			expect(screen.getByTestId('toolbar-print-check-result').textContent).toContain('4 pages');
			expect(screen.getByTestId('toolbar-print-check-result').textContent).toContain(
				'Block practice-stack is taller than one A4 page.'
			);
			expect(screen.getByTestId('toolbar-page-count').textContent?.trim()).toBe('4 pages');
		});
	});
});
