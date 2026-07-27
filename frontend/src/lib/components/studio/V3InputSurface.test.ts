import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const { getProfile, narrowTopic, proposeIntent } = vi.hoisted(() => ({
	getProfile: vi.fn(),
	narrowTopic: vi.fn(),
	proposeIntent: vi.fn()
}));
vi.mock('$lib/api/profile', () => ({ getProfile }));
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
const debounce = () => new Promise((resolve) => setTimeout(resolve, 650));

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((done) => { resolve = done; });
	return { promise, resolve };
}

async function fillClassAndTopic(): Promise<void> {
	const grade = screen.getByLabelText('Grade level') as HTMLSelectElement;
	grade.value = 'Grade 6'; await fireEvent.change(grade);
	const subject = screen.getByLabelText('Subject') as HTMLSelectElement;
	subject.value = 'Mathematics'; await fireEvent.change(subject);
	const topic = screen.getByLabelText('Topic') as HTMLInputElement;
	topic.value = 'Finding the area of irregular shapes'; await fireEvent.input(topic);
}

afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
	getProfile.mockReset();
	narrowTopic.mockReset();
	proposeIntent.mockReset();
});

describe('V3InputSurface', () => {
	it('renders the five proposed cards in order', () => {
		getProfile.mockRejectedValue(new Error('not available'));
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		const labels = screen.getAllByText(/Step [1-5] \//).map((element) => element.textContent);
		expect(labels).toEqual(['Step 1 / Class shape', 'Step 2 / Lesson shape', 'Step 3 / Topic', 'Step 4 / Intent', 'Step 5 / Anything else']);
		expect(screen.getByLabelText('Grade level')).toBeTruthy();
		expect(screen.getByLabelText('Topic')).toBeTruthy();
	});

	it('prefills a short class label from the profile and leaves long descriptions blank', async () => {
		getProfile.mockResolvedValueOnce({ default_audience_description: '  Year 7 Science  ' });
		const { unmount } = render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await waitFor(() => expect((screen.getByLabelText('Class') as HTMLInputElement).value).toBe('Year 7 Science'));
		unmount();

		getProfile.mockResolvedValueOnce({ default_audience_description: 'A mixed class with a detailed description that is too long' });
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await waitFor(() => expect(getProfile).toHaveBeenCalledTimes(2));
		expect((screen.getByLabelText('Class') as HTMLInputElement).value).toBe('');
	});

	it('submits the optional class label separately from the planning form', async () => {
		getProfile.mockRejectedValue(new Error('not available'));
		narrowTopic.mockResolvedValue(candidates);
		proposeIntent.mockResolvedValue(drafts);
		const onSubmit = vi.fn();
		render(V3InputSurface, { props: { onSubmit } });
		await fillClassAndTopic();
		await debounce();
		await fireEvent.click(screen.getByRole('button', { name: /use this topic/i }));
		await waitFor(() => expect((screen.getByLabelText('Desired outcome') as HTMLTextAreaElement).disabled).toBe(false));
		const classInput = screen.getByLabelText('Class') as HTMLInputElement;
		classInput.value = '  Year 6 Mathematics  ';
		await fireEvent.input(classInput);
		const outcome = screen.getByLabelText('Desired outcome') as HTMLTextAreaElement;
		outcome.value = 'Students calculate irregular areas.';
		await fireEvent.input(outcome);

		await fireEvent.click(screen.getByRole('button', { name: 'Build the skeleton' }));

		expect(onSubmit).toHaveBeenCalledWith(
			expect.objectContaining({
				grade_level: 'Grade 6',
				subject: 'Mathematics',
				topic: 'Finding the area of irregular shapes'
			}),
			'Year 6 Mathematics'
		);
		expect(onSubmit.mock.calls[0][0]).not.toHaveProperty('class_label');
	});

	it('soft-gates intent, context, and submit until the topic is confirmed', async () => {
		narrowTopic.mockResolvedValue(candidates);
		proposeIntent.mockResolvedValue(drafts);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });

		expect((screen.getByLabelText('Desired outcome') as HTMLTextAreaElement).disabled).toBe(true);
		expect((screen.getByLabelText('Likely struggle') as HTMLTextAreaElement).disabled).toBe(true);
		expect((screen.getByLabelText('What have they already covered?') as HTMLTextAreaElement).disabled).toBe(true);
		expect((screen.getByLabelText('Anything else to keep in mind?') as HTMLTextAreaElement).disabled).toBe(true);
		expect((screen.getByRole('button', { name: 'Build the skeleton' }) as HTMLButtonElement).disabled).toBe(true);
		expect(screen.getByText('Confirm your topic above to draft the lesson intent.')).toBeTruthy();
		expect(screen.getByText('Available after the topic is confirmed.')).toBeTruthy();

		await fillClassAndTopic(); await debounce();
		await fireEvent.click(screen.getByRole('button', { name: /use this topic/i }));
		await waitFor(() => expect((screen.getByLabelText('Desired outcome') as HTMLTextAreaElement).disabled).toBe(false));
		expect((screen.getByLabelText('Anything else to keep in mind?') as HTMLTextAreaElement).disabled).toBe(false);
	});

	it('narrows a valid topic from input after the debounce', async () => {
		narrowTopic.mockResolvedValue(candidates);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic();
		await waitFor(() => expect(narrowTopic).toHaveBeenCalledWith({ topic: 'Finding the area of irregular shapes', grade_level: 'Grade 6', subject: 'Mathematics' }), { timeout: 1000 });
		expect(await screen.findByText('Decompose into rectangles')).toBeTruthy();
	});

	it('shows a prerequisite hint instead of narrowing without grade and subject', async () => {
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		const topic = screen.getByLabelText('Topic') as HTMLInputElement;
		topic.value = 'Equivalent fractions'; await fireEvent.input(topic);
		expect(screen.getByText('Pick a grade and subject first.')).toBeTruthy();
		expect(narrowTopic).not.toHaveBeenCalled();
	});

	it('discards an in-flight narrowing result when the topic changes', async () => {
		const first = deferred<typeof candidates>();
		const currentCandidates = [{ id: 'coordinates', title: 'Coordinate grid area', description: 'Use coordinates to calculate area.' }];
		narrowTopic.mockImplementationOnce(() => first.promise).mockResolvedValueOnce(currentCandidates);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic();
		await waitFor(() => expect(narrowTopic).toHaveBeenCalledTimes(1), { timeout: 1000 });

		const topic = screen.getByLabelText('Topic') as HTMLInputElement;
		topic.value = 'Finding area on coordinate grids'; await fireEvent.input(topic);
		first.resolve(candidates);
		await tick();
		expect(screen.queryByText('Decompose into rectangles')).toBeNull();
		await waitFor(() => expect(narrowTopic).toHaveBeenCalledTimes(2), { timeout: 1000 });
		expect(await screen.findByText('Coordinate grid area')).toBeTruthy();
	});

	it('shows inline chip descriptions and limits selection to four', async () => {
		narrowTopic.mockResolvedValue(candidates);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await debounce();
		await waitFor(() => expect(screen.getByText(candidates[0].description)).toBeTruthy());
		for (const candidate of candidates.slice(0, 4)) await fireEvent.click(screen.getByRole('button', { name: new RegExp(candidate.title) }));
		expect((screen.getByRole('button', { name: /compare strategies/i }) as HTMLButtonElement).disabled).toBe(true);
		expect(proposeIntent).not.toHaveBeenCalled();
	});

	it('prefills the editable intent fields only after explicit topic confirmation', async () => {
		narrowTopic.mockResolvedValue(candidates); proposeIntent.mockResolvedValue(drafts);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await debounce();
		await fireEvent.click(screen.getByRole('button', { name: /decompose into rectangles/i }));
		expect(proposeIntent).not.toHaveBeenCalled();
		await fireEvent.click(screen.getByRole('button', { name: /use this topic/i }));
		await waitFor(() => expect(proposeIntent).toHaveBeenCalled());
		expect(proposeIntent).toHaveBeenCalledTimes(1);
		expect(proposeIntent).toHaveBeenCalledWith(expect.objectContaining({ subtopics: ['Decompose into rectangles'] }));
		expect((screen.getByLabelText('Desired outcome') as HTMLTextAreaElement).value).toBe(drafts.outcome_draft);
		expect((screen.getByLabelText('What have they already covered?') as HTMLTextAreaElement).value).toBe(drafts.prior_knowledge_draft);
	});

	it('can confirm an empty candidate result and skip selected suggestions', async () => {
		narrowTopic.mockResolvedValueOnce([]).mockResolvedValueOnce(candidates);
		proposeIntent.mockResolvedValue(drafts);
		const { unmount } = render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await debounce();
		await fireEvent.click(screen.getByRole('button', { name: /use this topic/i }));
		await waitFor(() => expect(proposeIntent).toHaveBeenCalledTimes(1));
		unmount();

		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await debounce();
		await fireEvent.click(screen.getByRole('button', { name: /decompose into rectangles/i }));
		await fireEvent.click(screen.getByRole('button', { name: /skip suggestions/i }));
		await waitFor(() => expect(proposeIntent).toHaveBeenCalledTimes(2));
		expect(proposeIntent.mock.calls[1][0].subtopics).toEqual([]);
	});

	it('shows a stale refresh pill and confirms before overwriting edits', async () => {
		narrowTopic.mockResolvedValue(candidates); proposeIntent.mockResolvedValue(drafts);
		const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
		render(V3InputSurface, { props: { onSubmit: vi.fn() } });
		await fillClassAndTopic(); await debounce();
		await fireEvent.click(screen.getByRole('button', { name: /use this topic/i }));
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
