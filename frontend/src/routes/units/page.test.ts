// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	listUnits: vi.fn(),
	listLegacyUnitWrappers: vi.fn(),
	createUnit: vi.fn(),
	goto: vi.fn()
}));
vi.mock('$app/navigation', () => ({ goto: mocks.goto }));
vi.mock('$lib/api/units', () => ({
	listUnits: mocks.listUnits,
	listLegacyUnitWrappers: mocks.listLegacyUnitWrappers,
	createUnit: mocks.createUnit
}));

import UnitsPage from './+page.svelte';

describe('/units', () => {
	beforeEach(() => {
		Object.values(mocks).forEach((mock) => mock.mockReset());
		mocks.listUnits.mockResolvedValue([]);
		mocks.listLegacyUnitWrappers.mockResolvedValue([]);
	});

	it('shows existing packs as computed one-lesson units', async () => {
		mocks.listLegacyUnitWrappers.mockResolvedValue([{
			id: 'legacy:pack-1', kind: 'legacy_unit', legacy_pack_id: 'pack-1',
			title: 'Cells', subject: 'Science', destination_objective: 'Explain cells.',
			status: 'ready', resource_count: 2, completed_count: 2,
			created_at: '2026-08-01T00:00:00Z', computed: true, migration_required: false,
			lesson: { title: 'Cells', pack_id: 'pack-1', generation_ids: [], open_href: '/packs/pack-1' }
		}]);

		render(UnitsPage);
		expect(await screen.findByRole('heading', { name: 'Legacy one-lesson units' })).toBeTruthy();
		expect(screen.getByRole('link', { name: /Cells/ }).getAttribute('href')).toBe('/packs/pack-1');
		expect(screen.getByText('Computed views of existing packs. No data was migrated or rewritten.')).toBeTruthy();
	});
	afterEach(cleanup);

	it('makes the destination-led unit workflow visible', async () => {
		render(UnitsPage);
		expect(await screen.findByText('No units yet')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Create your first unit' }));
		expect(screen.getByRole('heading', { name: 'Define the destination' })).toBeTruthy();
		expect(screen.getByText('No lesson count or duration is sent to path planning.')).toBeTruthy();
	});

	it('creates a unit and opens its workspace', async () => {
		mocks.createUnit.mockResolvedValue({ id: 'unit-1' });
		render(UnitsPage);
		await screen.findByText('No units yet');
		await fireEvent.click(screen.getByRole('button', { name: 'Create your first unit' }));
		await fireEvent.input(screen.getByLabelText('Unit title'), { target: { value: 'Photosynthesis' } });
		await fireEvent.input(screen.getByLabelText('Topic'), { target: { value: 'Plant food' } });
		await fireEvent.input(screen.getByLabelText('Subject'), { target: { value: 'Science' } });
		await fireEvent.input(screen.getByLabelText('Grade level'), { target: { value: 'Grade 7' } });
		await fireEvent.input(screen.getByLabelText('Destination objective'), { target: { value: 'Explain how plants make food.' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Create unit' }));

		await waitFor(() => expect(mocks.goto).toHaveBeenCalledWith('/units/unit-1'));
		expect(mocks.createUnit.mock.calls[0][0]).not.toHaveProperty('duration_minutes');
	});
});
