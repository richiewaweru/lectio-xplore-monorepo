import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it, vi } from 'vitest';

const { narrowTopic } = vi.hoisted(() => ({
	narrowTopic: vi.fn()
}));

vi.mock('$lib/api/v3', () => ({
	narrowTopic
}));

import V3InputSurface from './V3InputSurface.svelte';


describe('V3InputSurface', () => {
	it('submits a comprehensive V3InputForm payload', async () => {
		const onSubmit = vi.fn();
		render(V3InputSurface, { props: { onSubmit } });

		const gradeSelect = screen.getByLabelText('Grade level') as HTMLSelectElement;
		gradeSelect.value = 'Grade 7';
		await fireEvent.change(gradeSelect);
		await tick();

		const subjectSelect = screen.getByLabelText('Subject') as HTMLSelectElement;
		subjectSelect.value = 'Mathematics';
		await fireEvent.change(subjectSelect);
		await tick();

		const topicInput = screen.getByLabelText('Topic') as HTMLInputElement;
		topicInput.value = 'Compound area';
		await fireEvent.input(topicInput);
		await tick();

		const outcomeInput = screen.getByLabelText('Desired outcome') as HTMLTextAreaElement;
		outcomeInput.value = 'Students can break compound shapes into rectangles and find the total area.';
		await fireEvent.input(outcomeInput);
		await tick();

		const submit = screen.getByRole('button', { name: 'Build the skeleton' }) as HTMLButtonElement;
		expect(submit.disabled).toBe(false);

		await fireEvent.click(submit);
		await tick();

		expect(onSubmit).toHaveBeenCalledTimes(1);
		const payload = onSubmit.mock.calls[0][0];
		expect(payload.grade_level).toBe('Grade 7');
		expect(payload.topic).toBe('Compound area');
		expect(Array.isArray(payload.subtopics)).toBe(true);
		expect(payload.resource_type).toBeDefined();
		expect(payload.outcome).toContain('compound shapes');
		expect(payload.learner_level).toBeDefined();
	});

	it('calls narrowTopic with topic, grade_level, and subject when Narrow is clicked', async () => {
		narrowTopic.mockResolvedValue([
			{ id: 'seed-dispersal', title: 'Seed dispersal', description: 'How plants spread seeds.' },
			{ id: 'pollination', title: 'Pollination', description: 'Role of insects.' }
		]);

		render(V3InputSurface, { props: { onSubmit: vi.fn() } });

		const gradeSelect = screen.getByLabelText('Grade level') as HTMLSelectElement;
		gradeSelect.value = 'Grade 6';
		await fireEvent.change(gradeSelect);

		const subjectSelect = screen.getByLabelText('Subject') as HTMLSelectElement;
		subjectSelect.value = 'Biology';
		await fireEvent.change(subjectSelect);

		const topicInput = screen.getByLabelText('Topic') as HTMLInputElement;
		topicInput.value = 'Reproduction in plants';
		await fireEvent.input(topicInput);

		await fireEvent.click(screen.getByRole('button', { name: /narrow/i }));

		expect(narrowTopic).toHaveBeenCalledWith({
			topic: 'Reproduction in plants',
			grade_level: 'Grade 6',
			subject: 'Biology'
		});
	});

	it('shows chips from narrowTopic response after Narrow is clicked', async () => {
		narrowTopic.mockResolvedValue([
			{ id: 'seed-dispersal', title: 'Seed dispersal', description: 'How plants spread seeds.' },
			{ id: 'pollination', title: 'Pollination', description: 'Role of insects.' }
		]);

		render(V3InputSurface, { props: { onSubmit: vi.fn() } });

		const gradeSelect = screen.getByLabelText('Grade level') as HTMLSelectElement;
		gradeSelect.value = 'Grade 6';
		await fireEvent.change(gradeSelect);

		const subjectSelect = screen.getByLabelText('Subject') as HTMLSelectElement;
		subjectSelect.value = 'Biology';
		await fireEvent.change(subjectSelect);

		const topicInput = screen.getByLabelText('Topic') as HTMLInputElement;
		topicInput.value = 'Reproduction in plants';
		await fireEvent.input(topicInput);

		await fireEvent.click(screen.getByRole('button', { name: /narrow/i }));

		await waitFor(() => {
			expect(screen.getByText('Seed dispersal')).toBeTruthy();
			expect(screen.getByText('Pollination')).toBeTruthy();
		});
	});

	it('runs local split fallback when narrowTopic rejects for "Seeds, Pollination"', async () => {
		narrowTopic.mockRejectedValue(new Error('Network error'));

		render(V3InputSurface, { props: { onSubmit: vi.fn() } });

		const gradeSelect = screen.getByLabelText('Grade level') as HTMLSelectElement;
		gradeSelect.value = 'Grade 6';
		await fireEvent.change(gradeSelect);

		const subjectSelect = screen.getByLabelText('Subject') as HTMLSelectElement;
		subjectSelect.value = 'Biology';
		await fireEvent.change(subjectSelect);

		const topicInput = screen.getByLabelText('Topic') as HTMLInputElement;
		topicInput.value = 'Seeds, Pollination';
		await fireEvent.input(topicInput);

		await fireEvent.click(screen.getByRole('button', { name: /narrow/i }));

		await waitFor(() => {
			expect(screen.getByText('Seeds')).toBeTruthy();
		});
	});
});
