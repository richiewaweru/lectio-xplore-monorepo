import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import OrderedDocumentList from './OrderedDocumentList.svelte';
import type { LearnDocument } from '$lib/learn/document/types';

const longTitle = 'How a plant makes its own food: photosynthesis in the leaves';

describe('lesson map', () => {
	it('keeps the full long title text in a wrapping map item', () => {
		const document = {
			nodes: [],
			sections: [{ id: 's1', title: longTitle, position: 1, node_ids: [] }]
		} as unknown as LearnDocument;
		render(OrderedDocumentList, { document, preview: true });
		const label = within(screen.getByTestId('runtime-section-tabs')).getByText(longTitle);
		expect(label.closest('button')?.textContent).toContain(longTitle);
		expect(label.closest('li')).toBeTruthy();
	});
});

describe('figure numbering', () => {
	it('numbers figures cumulatively across sections', () => {
		const document = {
			nodes: [
				{ id: 'f1', kind: 'figure', caption: 'First', alt: 'a', asset_id: 'https://cdn.example.test/a.png' },
				{ id: 'f2', kind: 'figure', caption: 'Second', alt: 'b', asset_id: 'https://cdn.example.test/b.png' }
			],
			sections: [
				{ id: 's1', title: 'One', position: 1, node_ids: ['f1'] },
				{ id: 's2', title: 'Two', position: 2, node_ids: ['f2'] }
			]
		} as unknown as LearnDocument;
		const { container } = render(OrderedDocumentList, { document, preview: true });
		const text = container.querySelector('.lesson-sections')?.textContent ?? '';
		expect(text).toContain('Figure 1');
		expect(text).toContain('Figure 2');
		expect(text.match(/Figure 1/g)?.length).toBe(1);
	});
});

const threeSections = {
	nodes: [
		{ id: 'f1', kind: 'figure', caption: 'First', alt: 'a', asset_id: 'https://cdn.example.test/a.png' },
		{ id: 'f2', kind: 'figure', caption: 'Second', alt: 'b', asset_id: 'https://cdn.example.test/b.png' },
		{ id: 'f3', kind: 'figure', caption: 'Third', alt: 'c', asset_id: 'https://cdn.example.test/c.png' }
	],
	sections: [
		{ id: 's1', title: 'Alpha part', position: 1, node_ids: ['f1'] },
		{ id: 's2', title: 'Beta part', position: 2, node_ids: ['f2'] },
		{ id: 's3', title: 'Gamma part', position: 3, node_ids: ['f3'] }
	]
} as unknown as LearnDocument;

function content(container: HTMLElement): string {
	return container.querySelector('.section-content')?.textContent ?? '';
}

describe('learner section player', () => {
	it('opens at the first section for a new learner and has no All sections button', () => {
		const { container } = render(OrderedDocumentList, { document: threeSections });
		expect(content(container)).toContain('Figure 1');
		expect(container.querySelectorAll('.section-content').length).toBe(1);
		expect(screen.queryByText('All sections')).toBeNull();
		expect(screen.queryByTestId('section-prev')).toBeNull();
	});

	it('resumes at the section after the last completed one', () => {
		const { container } = render(OrderedDocumentList, {
			document: threeSections,
			initialCompletedSectionIds: ['s1']
		});
		// Task/figure numbering is computed across all sections, so this is Figure 2.
		expect(content(container)).toContain('Figure 2');
		expect(content(container)).not.toContain('Figure 1');
	});

	it('moves with Next and Previous and marks the section left as visited', async () => {
		const onSectionChange = vi.fn();
		const { container } = render(OrderedDocumentList, { document: threeSections, onSectionChange });
		await fireEvent.click(screen.getByTestId('section-next'));
		expect(onSectionChange).toHaveBeenCalledWith('s1');
		expect(content(container)).toContain('Figure 2');
		await fireEvent.click(screen.getByTestId('section-prev'));
		expect(content(container)).toContain('Figure 1');
		expect(onSectionChange).toHaveBeenCalledTimes(1);
		expect(onSectionChange).not.toHaveBeenCalledWith('all');
	});

	it('lets the map jump back to reached sections but not ahead', async () => {
		const { container } = render(OrderedDocumentList, {
			document: threeSections,
			initialCompletedSectionIds: ['s1']
		});
		const map = screen.getByTestId('runtime-section-tabs');
		const buttons = within(map).getAllByRole('button') as HTMLButtonElement[];
		expect(buttons.map((b) => b.disabled)).toEqual([false, false, true]);
		await fireEvent.click(buttons[0]);
		expect(content(container)).toContain('Figure 1');
		await fireEvent.click(buttons[2]);
		expect(content(container)).toContain('Figure 1');
	});
});

describe('last section', () => {
	async function lastSection(props: Record<string, unknown>) {
		const view = render(OrderedDocumentList, {
			document: threeSections,
			initialCompletedSectionIds: ['s1', 's2'],
			...props
		});
		return view;
	}

	it('links to the next lesson when it is ready', async () => {
		await lastSection({ nextLesson: { state: 'ready', title: 'T', instance_id: 'inst-9', number: 4 } });
		const link = screen.getByTestId('next-lesson-ready') as HTMLAnchorElement;
		expect(link.textContent).toContain('Lesson 4 is ready');
		expect(link.getAttribute('href')).toBe('/learn/instances/inst-9');
		expect(screen.queryByTestId('section-next')).toBeNull();
	});

	it('shows a non-link message when the next lesson is pending', async () => {
		await lastSection({ nextLesson: { state: 'pending', title: 'T', instance_id: null, number: 4 } });
		const note = screen.getByTestId('next-lesson-pending');
		expect(note.textContent).toContain('Lesson 4 is being prepared');
		expect(note.closest('a')).toBeNull();
	});

	it('offers Finish lesson when there is no next lesson', async () => {
		const onFinish = vi.fn();
		const onSectionChange = vi.fn();
		await lastSection({ nextLesson: { state: null }, onFinish, onSectionChange });
		await fireEvent.click(screen.getByTestId('finish-lesson'));
		await vi.waitFor(() => expect(onFinish).toHaveBeenCalledTimes(1));
		expect(onSectionChange).toHaveBeenCalledWith('s3');
	});

	it('also offers Finish lesson for an unlinked lesson (no topic)', async () => {
		await lastSection({});
		expect(screen.getByTestId('finish-lesson')).toBeTruthy();
	});
});

describe('teacher preview', () => {
	it('still shows All sections by default with every map item enabled', () => {
		const { container } = render(OrderedDocumentList, { document: threeSections, preview: true });
		expect(screen.getByText('All sections')).toBeTruthy();
		expect(container.querySelectorAll('.lesson-section').length).toBe(3);
		const buttons = within(screen.getByTestId('runtime-section-tabs')).getAllByRole('button') as HTMLButtonElement[];
		expect(buttons.every((b) => !b.disabled)).toBe(true);
		expect(screen.queryByTestId('section-nav')).toBeNull();
	});
});
