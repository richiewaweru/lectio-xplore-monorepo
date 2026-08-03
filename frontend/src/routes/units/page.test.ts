// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	listUnits: vi.fn(),
	listLegacyUnitWrappers: vi.fn(),
	createUnit: vi.fn(),
	constructorReadback: vi.fn(),
	planUnitPath: vi.fn(),
	goto: vi.fn()
}));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/api/units', () => ({
	listUnits: mocks.listUnits,
	listLegacyUnitWrappers: mocks.listLegacyUnitWrappers,
	createUnit: mocks.createUnit,
	constructorReadback: mocks.constructorReadback,
	planUnitPath: mocks.planUnitPath
}));

import UnitsPage from './+page.svelte';

describe('/units', () => {
	beforeEach(() => {
		Object.values(mocks).forEach((mock) => mock.mockReset());
		mocks.listUnits.mockResolvedValue([]);
		mocks.listLegacyUnitWrappers.mockResolvedValue([]);
	});
	afterEach(cleanup);

	it('shows existing packs as computed one-lesson units', async () => {
		mocks.listLegacyUnitWrappers.mockResolvedValue([{
			id: 'legacy:pack-1', kind: 'legacy_unit', legacy_pack_id: 'pack-1',
			title: 'Cells', subject: 'Science', destination_objective: 'Explain cells.',
			status: 'ready', resource_count: 2, completed_count: 2,
			created_at: '2026-08-01T00:00:00Z', computed: true, migration_required: false,
			lesson: { title: 'Cells', pack_id: 'pack-1', generation_ids: [], open_href: '/units/legacy/pack-1' }
		}]);

		render(UnitsPage);
		expect(await screen.findByRole('heading', { name: 'Legacy one-lesson units' })).toBeTruthy();
		expect(screen.getByRole('link', { name: /Cells/ }).getAttribute('href')).toBe('/units/legacy/pack-1');
		expect(screen.getByText('Computed views of existing packs. No data was migrated or rewritten.')).toBeTruthy();
	});

	it('shows the teacher-language empty state and opens the new-unit flow', async () => {
		render(UnitsPage);
		expect(await screen.findByText('No units yet')).toBeTruthy();
		expect(screen.getByText("Tell me what you're teaching and I'll plan the lessons.")).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Get started' }));
		expect(screen.getByRole('heading', { name: 'What are you teaching?' })).toBeTruthy();
		expect(screen.getByLabelText('Subject')).toBeTruthy();
		expect(screen.getByLabelText('Grade level')).toBeTruthy();
		expect(screen.getByLabelText('What are you teaching? Anything I should know about this class?')).toBeTruthy();
		expect(screen.queryByLabelText('Destination objective')).toBeNull();
		expect(screen.queryByLabelText('Starting knowledge')).toBeNull();
		expect(screen.queryByLabelText('Curriculum context')).toBeNull();
	});

	it('reads back a plan and creates the unit after "That\'s right"', async () => {
		mocks.constructorReadback.mockResolvedValue({
			destination_objective: 'Explain how plants make food.',
			starting_knowledge: ['Plants are living things.'],
			curriculum_context: null,
			class_notes: null,
			clarifying_question: null
		});
		mocks.createUnit.mockResolvedValue({ id: 'unit-1' });
		mocks.planUnitPath.mockResolvedValue({ id: 'path-1', lessons: [] });

		render(UnitsPage);
		await fireEvent.click(await screen.findByRole('button', { name: '+ New unit' }));
		await fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Science' } });
		await fireEvent.change(screen.getByLabelText('Grade level'), { target: { value: 'Grade 8' } });
		await fireEvent.input(
			screen.getByLabelText('What are you teaching? Anything I should know about this class?'),
			{ target: { value: 'Photosynthesis for my class.' } }
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Plan it' }));

		expect(await screen.findByText("Here's my understanding:")).toBeTruthy();
		expect(screen.getByText(/By the end, students can/)).toBeTruthy();
		expect(screen.getByText(/Explain how plants make food\./)).toBeTruthy();
		expect(screen.getByText(/I'm assuming they already know/)).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: "That's right" }));

		await waitFor(() => expect(mocks.createUnit).toHaveBeenCalled());
		expect(mocks.createUnit.mock.calls[0][0]).toEqual(
			expect.objectContaining({
				subject: 'Science',
				grade_level: 'Grade 8',
				destination_objective: 'Explain how plants make food.',
				starting_knowledge: ['Plants are living things.']
			})
		);
		await waitFor(() => expect(mocks.planUnitPath).toHaveBeenCalledWith('unit-1', expect.any(Object)));
		await waitFor(() => expect(mocks.goto).toHaveBeenCalledWith('/units/unit-1'));
	});

	it('asks the clarifying question first when the constructor returns one', async () => {
		mocks.constructorReadback.mockResolvedValueOnce({
			destination_objective: '',
			starting_knowledge: [],
			curriculum_context: null,
			class_notes: null,
			clarifying_question: 'Do you mean plant or animal cells?'
		});
		mocks.constructorReadback.mockResolvedValueOnce({
			destination_objective: 'Explain plant cell structure.',
			starting_knowledge: ['Cells are the building blocks of life.'],
			curriculum_context: null,
			class_notes: null,
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

		expect(await screen.findByText("Here's my understanding:")).toBeTruthy();
		expect(mocks.constructorReadback).toHaveBeenLastCalledWith(
			expect.objectContaining({ clarifying_answer: 'Plant cells' })
		);
	});

	it('re-reads the plan when the teacher types a correction', async () => {
		mocks.constructorReadback.mockResolvedValueOnce({
			destination_objective: 'Explain how plants make food.',
			starting_knowledge: ['Plants are living things.'],
			curriculum_context: null,
			class_notes: null,
			clarifying_question: null
		});
		mocks.constructorReadback.mockResolvedValueOnce({
			destination_objective: 'Explain cellular respiration in plants.',
			starting_knowledge: ['Plants are living things.'],
			curriculum_context: null,
			class_notes: null,
			clarifying_question: null
		});

		render(UnitsPage);
		await fireEvent.click(await screen.findByRole('button', { name: '+ New unit' }));
		await fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Science' } });
		await fireEvent.change(screen.getByLabelText('Grade level'), { target: { value: 'Grade 8' } });
		await fireEvent.input(
			screen.getByLabelText('What are you teaching? Anything I should know about this class?'),
			{ target: { value: 'Photosynthesis' } }
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Plan it' }));
		await screen.findByText("Here's my understanding:");

		await fireEvent.click(screen.getByRole('button', { name: "type what's off" }));
		await fireEvent.input(screen.getByPlaceholderText('What should I fix?'), {
			target: { value: 'I meant respiration, not photosynthesis.' }
		});
		await fireEvent.click(screen.getByRole('button', { name: 'Update' }));

		await waitFor(() => expect(screen.getByText(/Explain cellular respiration in plants\./)).toBeTruthy());
		expect(mocks.constructorReadback).toHaveBeenLastCalledWith(
			expect.objectContaining({ correction: 'I meant respiration, not photosynthesis.' })
		);
		expect(mocks.createUnit).not.toHaveBeenCalled();
	});
});
