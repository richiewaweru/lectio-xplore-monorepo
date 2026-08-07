// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	listUnits: vi.fn(),
	createUnit: vi.fn(),
	constructorReadback: vi.fn(),
	planUnitPath: vi.fn(),
	goto: vi.fn()
}));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/api/units', () => ({
	listUnits: mocks.listUnits,
	createUnit: mocks.createUnit,
	constructorReadback: mocks.constructorReadback,
	planUnitPath: mocks.planUnitPath
}));

import UnitsPage from './+page.svelte';

const readback = {
	title: 'Photosynthesis',
	topic: 'how plants make food',
	destination_objective: 'explain how plants make food',
	starting_knowledge: ['plants are living things'],
	curriculum_context: null,
	class_notes: null,
	clarifying_question: null
};

describe('/units', () => {
	beforeEach(() => {
		Object.values(mocks).forEach((mock) => mock.mockReset());
		mocks.listUnits.mockResolvedValue([]);
	});
	afterEach(cleanup);

	it('loads only v2 units and does not call legacy wrappers', async () => {
		render(UnitsPage);
		await screen.findByText('No units yet');
		expect(mocks.listUnits).toHaveBeenCalled();
		expect(screen.queryByRole('heading', { name: 'Legacy one-lesson units' })).toBeNull();
	});

	it('shows the teacher-language empty state and opens the new-unit flow', async () => {
		render(UnitsPage);
		expect(await screen.findByText('No units yet')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Get started' }));
		expect(screen.getByRole('heading', { name: 'What are you teaching?' })).toBeTruthy();
	});

	it('uses constructor title/topic and navigates even if planning fails', async () => {
		mocks.constructorReadback.mockResolvedValue(readback);
		mocks.createUnit.mockResolvedValue({ id: 'unit-1' });
		mocks.planUnitPath.mockRejectedValue(new Error('Planning failed'));

		render(UnitsPage);
		await fireEvent.click(await screen.findByRole('button', { name: '+ New unit' }));
		await fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Science' } });
		await fireEvent.change(screen.getByLabelText('Grade level'), { target: { value: 'Grade 8' } });
		await fireEvent.input(
			screen.getByLabelText('What are you teaching? Anything I should know about this class?'),
			{ target: { value: 'Photosynthesis for my class.' } }
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Plan it' }));

		expect(await screen.findByRole('heading', { name: 'Photosynthesis' })).toBeTruthy();
		expect(screen.getByText(/By the end, students can/)).toBeTruthy();
		expect(screen.getByText(/explain how plants make food/)).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: "That's right" }));

		await waitFor(() => expect(mocks.createUnit).toHaveBeenCalled());
		expect(mocks.createUnit.mock.calls[0][0]).toEqual(
			expect.objectContaining({
				title: 'Photosynthesis',
				topic: 'how plants make food',
				subject: 'Science',
				destination_objective: 'explain how plants make food'
			})
		);
		await waitFor(() => expect(mocks.goto).toHaveBeenCalledWith('/units/unit-1'));
	});

	it('asks the clarifying question first when the constructor returns one', async () => {
		mocks.constructorReadback.mockResolvedValueOnce({
			...readback,
			title: '',
			topic: '',
			destination_objective: '',
			starting_knowledge: [],
			clarifying_question: 'Do you mean plant or animal cells?'
		});
		mocks.constructorReadback.mockResolvedValueOnce({
			...readback,
			title: 'Plant Cells',
			topic: 'plant cell structure',
			destination_objective: 'explain plant cell structure',
			clarifying_question: null
		});

		render(UnitsPage);
		await fireEvent.click(await screen.findByRole('button', { name: '+ New unit' }));
		await fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Science' } });
		await fireEvent.change(screen.getByLabelText('Grade level'), { target: { value: 'Grade 8' } });
		await fireEvent.input(
			screen.getByLabelText('What are you teaching? Anything I should know about this class?'),
			{ target: { value: 'Cells' } }
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Plan it' }));

		expect(await screen.findByRole('heading', { name: 'Do you mean plant or animal cells?' })).toBeTruthy();
		await fireEvent.input(screen.getByLabelText('Your answer'), { target: { value: 'Plant cells' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Continue' }));

		expect(await screen.findByRole('heading', { name: 'Plant Cells' })).toBeTruthy();
	});
});
