import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LessonIssue, LessonIssueCounts } from '$lib/types/units';

vi.mock('$lib/api/units', () => ({
	dismissLessonIssue: vi.fn(),
	restoreLessonIssue: vi.fn()
}));

import { dismissLessonIssue, restoreLessonIssue } from '$lib/api/units';
import LessonIssuesPanel from './LessonIssuesPanel.svelte';

function issue(overrides: Partial<LessonIssue>): LessonIssue {
	return {
		id: 'x',
		path: 'learn',
		severity: 'warning',
		category: 'document',
		code: 'answer_leakage',
		message: 'A task answer may be given away.',
		repairable: false,
		source: 'semantic_qa',
		group: 'needs_look',
		section_id: 'sec-opaque-9f3',
		section_title: 'Practice',
		suggestion: 'Check the wording before the task.',
		details: 'Prose before task-3 states the answer 42.',
		dismissible: true,
		dismissed: false,
		...overrides
	};
}

const blocking = issue({
	id: 'b',
	severity: 'error',
	category: 'realization',
	code: 'REALIZATION_FAILED',
	message: "This lesson didn't finish building.",
	group: 'blocking',
	section_id: null,
	section_title: null,
	repairable: true,
	dismissible: false,
	details: 'writer failed: provider timeout',
	source: 'realization_status'
});
const boundary = issue({
	id: 'n',
	code: 'boundary_transition_warning',
	message: 'The move from Warm up into Worked example may feel abrupt.',
	section_id: 'sec-opaque-2',
	section_title: 'Worked example',
	details: null
});
const leak = issue({ id: 'a' });
const note = issue({
	id: 'i',
	severity: 'info',
	group: 'info',
	code: 'SLOPE_NOTE',
	message: 'A small note.',
	dismissible: false,
	section_id: null,
	section_title: null
});

function counts(over: Partial<LessonIssueCounts> = {}): LessonIssueCounts {
	return {
		info: 0,
		warning: 0,
		error: 0,
		blocking: 0,
		needs_look: 0,
		informational: 0,
		dismissed: 0,
		attention: 0,
		...over
	};
}

describe('LessonIssuesPanel', () => {
	afterEach(() => {
		cleanup();
		vi.clearAllMocks();
	});

	it('shows an explicit empty state', () => {
		render(LessonIssuesPanel, { props: { issues: [] } });
		expect(screen.getByTestId('no-issues').textContent).toContain('No issues detected');
	});

	it('keeps "No issues detected" when only info items exist and shows them collapsed', () => {
		render(LessonIssuesPanel, { props: { issues: [note] } });
		expect(screen.getByTestId('no-issues')).toBeTruthy();
		const group = screen.getByTestId('info-group') as HTMLDetailsElement;
		expect(group.open).toBe(false);
		expect(within(group).getByText('A small note.')).toBeTruthy();
	});

	it('orders groups blocking, needs a look, info, then marked as fine, and counts attention', () => {
		const fine = issue({ id: 'f', dismissed: true, message: 'Already fine.' });
		render(LessonIssuesPanel, {
			props: { issues: [note, boundary, blocking, leak, fine], counts: counts({ attention: 3 }) }
		});
		const order = ['group-blocking', 'group-needs-look', 'info-group', 'group-dismissed'].map((id) =>
			screen.getByTestId(id)
		);
		for (let i = 0; i < order.length - 1; i += 1) {
			expect(order[i].compareDocumentPosition(order[i + 1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		}
		expect(screen.getByTestId('attention-count').textContent).toBe('3 need attention');
		expect((screen.getByTestId('group-dismissed') as HTMLDetailsElement).open).toBe(false);
	});

	it('derives the attention count from unresolved blocking and needs-look items', () => {
		const fine = issue({ id: 'f', dismissed: true });
		render(LessonIssuesPanel, { props: { issues: [blocking, leak, note, fine] } });
		expect(screen.getByTestId('attention-count').textContent).toBe('2 need attention');
	});

	it('renders teacher language: section title and sentence, no ids, codes only under Details', () => {
		render(LessonIssuesPanel, { props: { issues: [leak, blocking], editBaseHref: '/builder/l1' } });
		const items = screen.getAllByTestId('issue-item');
		const leakItem = items.find((el) => el.getAttribute('data-group') === 'needs_look')!;
		expect(within(leakItem).getByText('Practice')).toBeTruthy();
		expect(within(leakItem).getByText('A task answer may be given away.')).toBeTruthy();
		expect(within(leakItem).getByText('Check the wording before the task.')).toBeTruthy();
		// The raw code, details text and section id are never in the default view.
		const visible = leakItem.cloneNode(true) as HTMLElement;
		visible.querySelector('details')!.remove();
		expect(visible.textContent).not.toContain('answer_leakage');
		expect(visible.textContent).not.toContain('sec-opaque-9f3');
		expect(visible.textContent).not.toContain('task-3');
		const details = leakItem.querySelector('details')!;
		expect(details.open).toBe(false);
		expect(details.textContent).toContain('answer_leakage');
		// Whole-lesson blocking item has teacher wording and a neutral heading.
		const blockingItem = items.find((el) => el.getAttribute('data-group') === 'blocking')!;
		expect(within(blockingItem).getByText('Whole lesson')).toBeTruthy();
		expect(within(blockingItem).getByText("This lesson didn't finish building.")).toBeTruthy();
		const visibleBlocking = blockingItem.cloneNode(true) as HTMLElement;
		visibleBlocking.querySelector('details')!.remove();
		expect(visibleBlocking.textContent).not.toContain('provider timeout');
		expect(visibleBlocking.textContent).not.toContain('REALIZATION_FAILED');
	});

	it('keeps Retry for blocking items only, and only when allowed', () => {
		const onRetry = vi.fn();
		render(LessonIssuesPanel, {
			props: { onRetry, allowRetry: true, issues: [blocking, leak, boundary] }
		});
		const buttons = screen.getAllByRole('button', { name: 'Retry' });
		expect(buttons).toHaveLength(1);
		void fireEvent.click(buttons[0]);
		expect(onRetry).toHaveBeenCalledTimes(1);
	});

	it('does not offer Retry when retry is not allowed', () => {
		render(LessonIssuesPanel, { props: { onRetry: vi.fn(), allowRetry: false, issues: [blocking] } });
		expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull();
	});

	it('builds the Learn and Print "Go to section" links and hides them when not built', () => {
		const { unmount } = render(LessonIssuesPanel, {
			props: { issues: [leak], editBaseHref: '/builder/lesson-9' }
		});
		expect(screen.getByTestId('go-to-section').getAttribute('href')).toBe(
			'/builder/lesson-9?section=sec-opaque-9f3'
		);
		unmount();

		render(LessonIssuesPanel, {
			props: { issues: [{ ...leak, path: 'print' }], editBaseHref: '/studio/print/gen-4' }
		});
		expect(screen.getByTestId('go-to-section').getAttribute('href')).toBe(
			'/studio/print/gen-4?section=sec-opaque-9f3'
		);
		cleanup();

		render(LessonIssuesPanel, { props: { issues: [leak], editBaseHref: null } });
		expect(screen.queryByTestId('go-to-section')).toBeNull();
		cleanup();

		render(LessonIssuesPanel, {
			props: { issues: [{ ...leak, section_id: null }], editBaseHref: '/builder/lesson-9' }
		});
		expect(screen.queryByTestId('go-to-section')).toBeNull();
	});

	it('marks an item as fine through the API and moves it to the collapsed group', async () => {
		vi.mocked(dismissLessonIssue).mockResolvedValue({
			path: 'learn',
			issues: [blocking, { ...leak, dismissed: true }, boundary],
			counts: counts({ attention: 2, dismissed: 1 })
		});
		render(LessonIssuesPanel, {
			props: { issues: [blocking, leak, boundary], unitId: 'u1', lessonId: 'l1', path: 'learn' }
		});
		expect(screen.getByTestId('attention-count').textContent).toBe('3 need attention');
		const needsLook = screen.getByTestId('group-needs-look');
		const leakCard = within(needsLook).getAllByTestId('issue-item')[0];
		await fireEvent.click(within(leakCard).getByRole('button', { name: 'Mark as fine' }));

		await waitFor(() => expect(screen.getByTestId('group-dismissed')).toBeTruthy());
		expect(dismissLessonIssue).toHaveBeenCalledWith('u1', 'l1', 'learn', 'a');
		expect(screen.getByTestId('attention-count').textContent).toBe('2 need attention');
		expect(within(screen.getByTestId('group-needs-look')).queryByText('A task answer may be given away.')).toBeNull();
		expect(screen.getByText('Marked as fine (1)')).toBeTruthy();
	});

	it('restores a dismissed item through the API and moves it back', async () => {
		vi.mocked(restoreLessonIssue).mockResolvedValue({
			path: 'learn',
			issues: [leak],
			counts: counts({ attention: 1, needs_look: 1 })
		});
		render(LessonIssuesPanel, {
			props: {
				issues: [{ ...leak, dismissed: true }],
				unitId: 'u1',
				lessonId: 'l1',
				path: 'learn'
			}
		});
		const dismissedGroup = screen.getByTestId('group-dismissed');
		await fireEvent.click(within(dismissedGroup).getByRole('button', { name: 'Restore' }));
		await waitFor(() => expect(screen.getByTestId('group-needs-look')).toBeTruthy());
		expect(restoreLessonIssue).toHaveBeenCalledWith('u1', 'l1', 'learn', 'a');
		expect(screen.queryByTestId('group-dismissed')).toBeNull();
		expect(screen.getByTestId('attention-count').textContent).toBe('1 needs attention');
	});

	it('shows an error and keeps the item when marking fails', async () => {
		vi.mocked(dismissLessonIssue).mockRejectedValue(new Error('Could not mark this as fine.'));
		render(LessonIssuesPanel, {
			props: { issues: [leak], unitId: 'u1', lessonId: 'l1', path: 'learn' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Mark as fine' }));
		await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Could not mark'));
		expect(screen.getByText('A task answer may be given away.')).toBeTruthy();
	});

	it('only offers Mark as fine on needs-a-look items', () => {
		render(LessonIssuesPanel, {
			props: { issues: [blocking, leak, note], unitId: 'u1', lessonId: 'l1', path: 'learn' }
		});
		expect(screen.getAllByRole('button', { name: 'Mark as fine' })).toHaveLength(1);
	});
});
