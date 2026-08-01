// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ getLegacyUnitWrapper: vi.fn() }));
vi.mock('$app/state', () => ({ page: { params: { pack_id: 'pack-1' } } }));
vi.mock('$lib/api/units', () => ({ getLegacyUnitWrapper: mocks.getLegacyUnitWrapper }));

import LegacyUnitPage from './+page.svelte';

describe('/units/legacy/[pack_id]', () => {
	afterEach(cleanup);

	it('opens every existing resource through the Legacy Studio viewer', async () => {
		mocks.getLegacyUnitWrapper.mockResolvedValue({
			id: 'legacy:pack-1', kind: 'legacy_unit', legacy_pack_id: 'pack-1', title: 'Cells',
			subject: 'Science', destination_objective: 'Explain cells.', status: 'ready',
			resource_count: 2, completed_count: 2, created_at: '2026-08-01T00:00:00Z',
			computed: true, migration_required: false,
			lesson: { title: 'Cells', pack_id: 'pack-1', generation_ids: ['gen-1', 'gen-2'], open_href: '/units/legacy/pack-1' }
		});

		render(LegacyUnitPage);
		expect(await screen.findByRole('heading', { name: 'Cells' })).toBeTruthy();
		const links = screen.getAllByRole('link', { name: /Open in Legacy Studio/ });
		expect(links.map((link) => link.getAttribute('href'))).toEqual([
			'/studio/generations/gen-1', '/studio/generations/gen-2'
		]);
		expect(screen.getByText('This is a read-only view of the existing pack. No data was migrated or rewritten.')).toBeTruthy();
	});
});
