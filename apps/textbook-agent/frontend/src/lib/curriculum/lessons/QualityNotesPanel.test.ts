import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('$lib/api/shared-documents', () => ({ getQualityFlags: vi.fn() }));

import { getQualityFlags } from '$lib/api/shared-documents';
import QualityNotesPanel from './QualityNotesPanel.svelte';

const flag = {
	code: 'answer_leakage',
	severity: 'warning' as const,
	source: 'semantic_qa' as const,
	message: 'The worked example gives away the answer to the task.',
	section_id: 'section-2',
	node_ids: ['n1'],
	required_correction: 'Rephrase the example so it does not state the answer.'
};

describe('QualityNotesPanel', () => {
	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it('lists each flag with its section and suggestion, without blocking', async () => {
		vi.mocked(getQualityFlags).mockResolvedValue({ run_id: 'run-1', flags: [flag] });
		render(QualityNotesPanel, { props: { editableLessonId: 'lesson-1' } });
		await waitFor(() => expect(screen.getByTestId('quality-notes')).toBeTruthy());
		expect(screen.getByText('Quality notes (1)')).toBeTruthy();
		expect(screen.getByText(flag.message)).toBeTruthy();
		expect(screen.getByText('Section: section-2')).toBeTruthy();
		expect(screen.getByText(/Rephrase the example/)).toBeTruthy();
		expect(getQualityFlags).toHaveBeenCalledWith({ editableLessonId: 'lesson-1' });
	});

	it('shows the resolved section title instead of the raw section id', async () => {
		vi.mocked(getQualityFlags).mockResolvedValue({
			run_id: 'run-1',
			flags: [{ ...flag, section_title: 'Worked example' }]
		});
		render(QualityNotesPanel, { props: { editableLessonId: 'lesson-1' } });
		await waitFor(() => expect(screen.getByTestId('quality-notes')).toBeTruthy());
		expect(screen.getByText('Section: Worked example')).toBeTruthy();
		expect(screen.queryByText(/section-2/)).toBeNull();
	});

	it('loads by generation id for the print editor', async () => {
		vi.mocked(getQualityFlags).mockResolvedValue({ run_id: 'run-1', flags: [flag] });
		render(QualityNotesPanel, { props: { generationId: 'gen-1' } });
		await waitFor(() => expect(screen.getByTestId('quality-notes')).toBeTruthy());
		expect(getQualityFlags).toHaveBeenCalledWith({ generationId: 'gen-1' });
	});

	it('renders nothing when there are no flags or the request fails', async () => {
		vi.mocked(getQualityFlags).mockResolvedValue({ run_id: null, flags: [] });
		const { unmount } = render(QualityNotesPanel, { props: { editableLessonId: 'lesson-1' } });
		await waitFor(() => expect(getQualityFlags).toHaveBeenCalled());
		expect(screen.queryByTestId('quality-notes')).toBeNull();
		unmount();
		vi.mocked(getQualityFlags).mockRejectedValue(new Error('boom'));
		render(QualityNotesPanel, { props: { editableLessonId: 'lesson-2' } });
		await waitFor(() => expect(getQualityFlags).toHaveBeenCalledTimes(2));
		expect(screen.queryByTestId('quality-notes')).toBeNull();
	});
});
