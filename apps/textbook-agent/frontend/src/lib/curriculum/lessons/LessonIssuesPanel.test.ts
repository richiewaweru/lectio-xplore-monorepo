import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LessonIssuesPanel from './LessonIssuesPanel.svelte';

describe('LessonIssuesPanel', () => {
	afterEach(() => cleanup());

	it('shows an explicit empty state', () => {
		render(LessonIssuesPanel, { props: { issues: [] } });
		expect(screen.getByTestId('no-issues').textContent).toContain('No issues detected');
	});

	it('shows advisory and blocking issues, including non-repairable ones', () => {
		const onRetry = vi.fn();
		render(LessonIssuesPanel, { props: { onRetry, allowRetry: true, issues: [
			{ id: 'a', path: 'learn', severity: 'warning', category: 'coherence', code: 'COHERENCE', message: 'Check this', repairable: false, source: 'review' },
			{ id: 'b', path: 'learn', severity: 'error', category: 'document', code: 'DOC', message: 'Retry this', repairable: true, source: 'document' }
		] } });
		expect(screen.getByText('Check this')).toBeTruthy();
		expect(screen.getByText('Retry this')).toBeTruthy();
		expect(screen.getByText('2 need attention')).toBeTruthy();
		expect(screen.getAllByRole('button', { name: 'Retry' })).toHaveLength(1);
	});
});
