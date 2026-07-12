import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { narrowTopic, proposeIntent } = vi.hoisted(() => ({ narrowTopic: vi.fn(), proposeIntent: vi.fn() }));
vi.mock('$lib/api/v3', () => ({ narrowTopic, proposeIntent }));

import V3InputSurface from './V3InputSurface.svelte';

const candidates = [
	{ id: 'rectangles', title: 'Decompose into rectangles', description: 'Students split L-shapes into rectangles and add areas.' },
	{ id: 'triangles', title: 'Split with triangles', description: 'Students split shapes using triangles and rectangles.' },
	{ id: 'grid', title: 'Count grid squares', description: 'Students count square units using a grid.' },
	{ id: 'missing', title: 'Find missing areas', description: 'Students find a missing rectangle area from known measures.' },
	{ id: 'compare', title: 'Compare strategies', description: 'Students compare decomposition methods.' }
];
const drafts = {
	outcome_draft: 'By the end, students can decompose irregular shapes into rectangles and add their areas.',
	struggle_draft: 'Students may skip a region while splitting shapes. They need to label each part before adding.',
	prior_knowledge_draft: 'Area of a rectangle\nAdd whole numbers'
};

async function fillClassAndTopic(): Promise<void> {
	const grade = screen.getByLabelText('Grade level') as HTMLSelectElement;
	grade.value = 'Grade 6'; await fireEvent.change(grade);
	const subject = screen.getByLabelText('Subject') as HTMLSelectElement;
	subject.value = 'Mathematics'; await fireEvent.change(subject);
	const topic = screen.getByLabelText('Topic') as HTMLInputElement;
	topic.value = 'Finding the area of irregular shapes'; await fireEvent.input(topic);
}

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('V3InputSurface', () => {
	it('renders the five proposed cards in order', () => {
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		const labels = screen.getAllByText(/Step [1-5] \//).map((element) => element.textContent);
		expect(labels).toEqual(['Step 1 / Class shape', 'Step 2 / Lesson shape', 'Step 3 / Topic', 'Step 4 / Intent', 'Step 5 / Anything else']);
		expect(screen.getByLabelText('Grade level')).toBeTruthy();
		expect(screen.getByLabelText('Topic')).toBeTruthy();
	});

	it('narrows a valid topic on blur after the debounce', async () => {
		narrowTopic.mockResolvedValue(candidates);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic();
		await fireEvent.blur(screen.getByLabelText('Topic'));
		await waitFor(() => expect(narrowTopic).toHaveBeenCalledWith({ topic: 'Finding the area of irregular shapes', grade_level: 'Grade 6', subject: 'Mathematics' }), { timeout: 1000 });
		expect(screen.getByText('Decompose into rectangles')).toBeTruthy();
	});

	it('shows inline chip descriptions and limits selection to four', async () => {
		narrowTopic.mockResolvedValue(candidates);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await fireEvent.blur(screen.getByLabelText('Topic'));
		await new Promise((resolve) => setTimeout(resolve, 650));
		await waitFor(() => expect(screen.getByText(candidates[0].description)).toBeTruthy());
		for (const candidate of candidates.slice(0, 4)) await fireEvent.click(screen.getByRole('button', { name: new RegExp(candidate.title) }));
		expect((screen.getByRole('button', { name: /compare strategies/i }) as HTMLButtonElement).disabled).toBe(true);
	});

	it('prefills the editable intent fields after a topic is settled', async () => {
		narrowTopic.mockResolvedValue(candidates); proposeIntent.mockResolvedValue(drafts);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await fireEvent.blur(screen.getByLabelText('Topic'));
		await new Promise((resolve) => setTimeout(resolve, 650));
		await fireEvent.click(screen.getByRole('button', { name: /continue with topic/i }));
		await waitFor(() => expect(proposeIntent).toHaveBeenCalled());
		expect((screen.getByLabelText('Desired outcome') as HTMLTextAreaElement).value).toBe(drafts.outcome_draft);
		expect((screen.getByLabelText('What have they already covered?') as HTMLTextAreaElement).value).toBe(drafts.prior_knowledge_draft);
	});

	it('shows a stale refresh pill and confirms before overwriting edits', async () => {
		narrowTopic.mockResolvedValue(candidates); proposeIntent.mockResolvedValue(drafts);
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await fireEvent.blur(screen.getByLabelText('Topic'));
		await new Promise((resolve) => setTimeout(resolve, 650));
		await fireEvent.click(screen.getByRole('button', { name: /continue with topic/i }));
		await waitFor(() => expect(screen.getByLabelText('Desired outcome')).toBeTruthy());
		const outcome = screen.getByLabelText('Desired outcome') as HTMLTextAreaElement;
		outcome.value = 'Teacher edit'; await fireEvent.input(outcome); await tick();
		const reading = screen.getByDisplayValue('At grade reading level') as HTMLSelectElement;
		reading.value = 'below_grade'; await fireEvent.change(reading);
		await fireEvent.click(screen.getByRole('button', { name: /refresh drafts/i }));
		expect(confirm).toHaveBeenCalled();
		expect(proposeIntent).toHaveBeenCalledTimes(1);
	});
});
