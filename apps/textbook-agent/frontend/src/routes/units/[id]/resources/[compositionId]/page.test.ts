// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const getUnitResource = vi.hoisted(() => vi.fn());
vi.mock('$app/state', () => ({
	page: {
		params: { id: 'unit-1', compositionId: 'composition-1' },
		url: new URL('http://test/units/unit-1/resources/composition-1')
	}
}));
vi.mock('$lib/api/units', () => ({ getUnitResource }));
vi.mock('$lib/print/components/studio/LectioPageDocumentView.svelte', async () => ({
	default: (await import('../../../../studio/__fixtures__/MockGeneric.svelte')).default
}));

import ResourcePage from './+page.svelte';

describe('/units/[id]/resources/[compositionId]', () => {
	afterEach(cleanup);

	it('loads a LectioDocument v2 projection into the page engine', async () => {
		getUnitResource.mockResolvedValue({
			id: 'composition-1',
			unit_id: 'unit-1',
			path_version_id: 'path-1',
			path_version: 1,
			path_revision: 1,
			projection: 'unit_exam',
			status: 'ready',
			lesson_ids: ['lesson-1'],
			period_ids: ['period-1'],
			group_ids: ['group-core'],
			selected_component_refs: [],
			selected_item_ids: ['item-1'],
			include_keys: true,
			template_version: 'resource-projection.v1',
			source_snapshots: [],
			document: {
				document_version: 2,
				id: 'composition-1',
				title: 'Projected assessment',
				subject: 'Science',
				sections: [
					{
						id: 'question-1',
						title: 'Projected assessment',
						blocks: [{ id: 'b1', type: 'paragraph', text: 'Where is food made?' }]
					}
				]
			}
		});

		render(ResourcePage);
		expect(await screen.findByRole('button', { name: 'Print' })).toBeTruthy();
		expect(await screen.findByText(/unit exam/i)).toBeTruthy();
	});

	it('rejects legacy SectionContent packs', async () => {
		getUnitResource.mockResolvedValue({
			id: 'composition-1',
			unit_id: 'unit-1',
			path_version_id: 'path-1',
			path_version: 1,
			path_revision: 1,
			projection: 'unit_exam',
			status: 'ready',
			lesson_ids: [],
			period_ids: [],
			group_ids: [],
			selected_component_refs: [],
			selected_item_ids: [],
			include_keys: true,
			template_version: 'resource-projection.v1',
			source_snapshots: [],
			document: {
				generation_id: 'composition-1',
				template_id: 'guided-concept-path',
				subject: 'Science',
				sections: []
			}
		});

		render(ResourcePage);
		expect(
			await screen.findByText(/no LectioDocument v2 payload/i)
		).toBeTruthy();
	});
});
