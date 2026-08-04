// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({ previewUnitResource: vi.fn(), createUnitResource: vi.fn() }));
vi.mock('$lib/api/units', () => mocks);

import ResourceComposerPanel from './ResourceComposerPanel.svelte';

const path = { id: 'path-1', revision: 3 } as never;
const lesson = { id: 'lesson-1', title: 'Plant inputs', pack_id: 'pack-1' } as never;
const groups = { groups: [{ id: 'group-core', label: 'Core', profile: 'core' }] } as never;
const preview = {
	id: null, unit_id: 'unit-1', path_version_id: 'path-1', path_version: 1, path_revision: 3,
	projection: 'revision_sheet', status: 'ready', can_create: true, unavailable_reasons: [],
	lesson_ids: ['lesson-1'], period_ids: [], group_ids: ['group-core'],
	selected_component_refs: ['generation-1:intro'], selected_item_ids: [],
	template_version: 'resource-v1', source_snapshots: [],
	available_components: [{ ref: 'generation-1:intro', path_lesson_id: 'lesson-1', lesson_title: 'Plant inputs', group_id: 'group-core', group_label: 'Core', section_id: 'intro', role: 'orient', title: 'Start here' }],
	available_items: [], document: { sections: [{ section_id: 'summary', header: { title: 'Revision summary' } }] }
};

describe('ResourceComposerPanel', () => {
	afterEach(cleanup);

	it('offers all projections and creates from approved selections', async () => {
		mocks.previewUnitResource.mockResolvedValue(preview);
		mocks.createUnitResource.mockResolvedValue({ ...preview, id: 'composition-1' });
		const oncreated = vi.fn();
		render(ResourceComposerPanel, { unitId: 'unit-1', path, lessons: [lesson], groups, schedule: null, compositions: [], oncreated });

		expect(screen.getAllByRole('radio')).toHaveLength(7);
		await fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
		expect(await screen.findByText('Start here')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Create resource' }));
		expect(mocks.createUnitResource).toHaveBeenCalledWith('unit-1', path, expect.objectContaining({
			projection: 'revision_sheet', component_refs: ['generation-1:intro']
		}));
		expect(oncreated).toHaveBeenCalledWith(expect.objectContaining({ id: 'composition-1' }));
	});

	it('surfaces projection_unavailable without enabling creation', async () => {
		mocks.previewUnitResource.mockResolvedValue({ ...preview, status: 'projection_unavailable', can_create: false, unavailable_reasons: ['Lesson preparation is stale.'] });
		render(ResourceComposerPanel, { unitId: 'unit-1', path, lessons: [lesson], groups, schedule: null, compositions: [], oncreated: vi.fn() });
		await fireEvent.click(screen.getByRole('button', { name: 'Preview' }));
		expect(await screen.findByText('Lesson preparation is stale.')).toBeTruthy();
		expect((screen.getByRole('button', { name: 'Create resource' }) as HTMLButtonElement).disabled).toBe(true);
	});
});
