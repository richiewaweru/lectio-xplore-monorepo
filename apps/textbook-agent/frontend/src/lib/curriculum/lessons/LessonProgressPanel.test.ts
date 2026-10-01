import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import LessonProgressPanel from './LessonProgressPanel.svelte';

afterEach(cleanup);

describe('LessonProgressPanel', () => {
	it('shows steps, the active label with counts, and the reassurance note', () => {
		render(LessonProgressPanel, {
			props: {
				progress: {
					steps: [
						{ key: 'sourcebook', label: 'Gathering source notes', status: 'done' },
						{ key: 'write', label: 'Writing sections', status: 'active', done: 2, total: 5 },
						{ key: 'document_qa', label: 'Final quality check', status: 'pending' }
					],
					current_label: 'Writing sections (2/5)',
					started_at: new Date(Date.now() - 65_000).toISOString()
				}
			}
		});
		const live = screen.getByTestId('lesson-progress-current');
		expect(live.getAttribute('aria-live')).toBe('polite');
		expect(live.textContent).toContain('Writing sections (2/5)');
		expect(screen.getAllByRole('listitem')).toHaveLength(3);
		expect(screen.getByTestId('lesson-progress-elapsed').textContent).toMatch(/1m/);
		expect(screen.getByText(/You can leave this page/)).toBeTruthy();
	});

	it('falls back gracefully without progress', () => {
		render(LessonProgressPanel, {
			props: { progress: null, fallbackTitle: 'Learn is being created' }
		});
		expect(screen.getByText('Learn is being created')).toBeTruthy();
		expect(screen.getByText('Getting started…')).toBeTruthy();
	});
});
