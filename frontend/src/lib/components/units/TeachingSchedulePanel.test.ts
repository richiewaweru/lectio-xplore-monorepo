// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	saveTeachingSchedule: vi.fn(),
	suggestTeachingSchedule: vi.fn()
}));

vi.mock('$lib/api/units', () => mocks);

import TeachingSchedulePanel from './TeachingSchedulePanel.svelte';

const lessons = [
	{ id: 'l1', title: 'One', concept_id: 'c1', objective: 'One', path_position: 0, estimated_minutes: 25 },
	{ id: 'l2', title: 'Two', concept_id: 'c2', objective: 'Two', path_position: 1, estimated_minutes: 40 },
	{ id: 'l3', title: 'Three', concept_id: 'c3', objective: 'Three', path_position: 2, estimated_minutes: 40 }
];

const schedule = {
	path_version_id: 'path-1', path_revision: 2, schedule_revision: 1,
	feasibility: { estimated_minutes: 105, planned_minutes: 100, delta_minutes: -5, status: 'overloaded' as const },
	periods: [
		{ id: 'p1', title: 'First', position: 1, planned_minutes: 50, teacher_note: null, lesson_ids: ['l1', 'l2'], lessons: lessons.slice(0, 2), feasibility: { estimated_minutes: 65, planned_minutes: 50, delta_minutes: -15, status: 'overloaded' as const } },
		{ id: 'p2', title: 'Second', position: 2, planned_minutes: 50, teacher_note: null, lesson_ids: ['l3'], lessons: lessons.slice(2), feasibility: { estimated_minutes: 40, planned_minutes: 50, delta_minutes: 10, status: 'tight' as const } }
	]
};

const path = {
	id: 'path-1', unit_id: 'unit-1', version: 1, revision: 2, status: 'approved', generated_by: 'planner',
	merge_critic_results: [], prerequisite_risks: [], forward_verified: true, reaches_destination: true,
	completeness_note: null, approved_at: null, created_at: '2026-08-01T00:00:00Z',
	lessons: lessons.map((lesson, index) => ({ ...lesson, concept_slug: `c.${index}`, objective_hash: 'hash', prerequisites: [], external_prerequisites: [], must_establish: ['x'], exclusions: [], primary_knowledge_type: 'conceptual' as const, secondary_demand: null, knowledge_type_source: 'planner', merge_warning: false, position: index, source: 'planner', teacher_edited: false, skipped: false, revision: 1, pack_id: null }))
};

describe('TeachingSchedulePanel', () => {
	afterEach(() => { cleanup(); vi.clearAllMocks(); });

	it('moves only a period boundary through an accessible control and preserves path order', async () => {
		mocks.saveTeachingSchedule.mockImplementation(async (_unitId, _path, value) => value);
		render(TeachingSchedulePanel, { unitId: 'unit-1', path, schedule, onsaved: vi.fn() });
		await fireEvent.click(screen.getByRole('button', { name: 'Move Two to next period' }));
		await fireEvent.click(screen.getByRole('button', { name: 'Save schedule' }));
		const saved = mocks.saveTeachingSchedule.mock.calls[0][2];
		expect(saved.periods.map((period: { lesson_ids: string[] }) => period.lesson_ids)).toEqual([
			['l1'], ['l2', 'l3']
		]);
		expect(saved.periods.flatMap((period: { lesson_ids: string[] }) => period.lesson_ids)).toEqual(['l1', 'l2', 'l3']);
	});

	it('updates feasibility immediately when planned time changes', async () => {
		render(TeachingSchedulePanel, { unitId: 'unit-1', path, schedule, onsaved: vi.fn() });
		const minutes = screen.getByRole('spinbutton', { name: 'Period 1 minutes' });
		await fireEvent.input(minutes, { target: { value: '80' } });
		expect(screen.getByText('65 min · comfortable')).toBeTruthy();
		expect(screen.getByText('comfortable', { selector: '.feasibility strong' })).toBeTruthy();
	});
});
