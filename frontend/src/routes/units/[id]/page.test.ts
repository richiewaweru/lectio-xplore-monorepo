// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	getUnit: vi.fn(), getUnitPath: vi.fn(), getLessonShape: vi.fn(),
	getTeachingSchedule: vi.fn(), getUnitGroups: vi.fn(), saveTeachingSchedule: vi.fn(),
	suggestTeachingSchedule: vi.fn(), saveUnitGroups: vi.fn(),
	getPathHistory: vi.fn(), getPathStatus: vi.fn(), getHistoricalPath: vi.fn(), restorePathVersion: vi.fn(),
	getPreparedLessonStatus: vi.fn(), approveUnitPath: vi.fn(), planUnitPath: vi.fn(),
	patchPathLesson: vi.fn(), skipPathLesson: vi.fn(), reorderPathLessons: vi.fn(),
	splitPathLesson: vi.fn(), mergePathLessons: vi.fn(), preparePathLesson: vi.fn(),
	regeneratePathLesson: vi.fn()
}));

vi.mock('$app/state', () => ({ page: { params: { id: 'unit-1' } } }));
vi.mock('$lib/api/units', () => mocks);

import UnitPage from './+page.svelte';

const unit = {
	id: 'unit-1', title: 'Photosynthesis', topic: 'Plant food', subject: 'Science',
	grade_level: 'Grade 7', curriculum_context: null,
	destination_objective: 'Explain how plants make food.', starting_knowledge: ['Plants are living.'],
	status: 'approved', active_path_version_id: 'path-1', groups_revision: 1
};
const lesson = {
	id: 'lesson-1', concept_id: 'concept-1', concept_slug: 'plant.food', title: 'Plant inputs',
	objective: 'Identify what plants need to make food.', objective_hash: 'hash', prerequisites: [],
	external_prerequisites: [], must_establish: ['plant inputs'], exclusions: [],
	primary_knowledge_type: 'factual', secondary_demand: null, knowledge_type_source: 'path_planner',
	merge_warning: false, position: 0, source: 'path_planner', teacher_edited: false,
	skipped: false, revision: 1, pack_id: 'generation-1'
};

describe('/units/[id]', () => {
	beforeEach(() => {
		Object.values(mocks).forEach((mock) => mock.mockReset());
		mocks.getUnit.mockResolvedValue(unit);
		mocks.getUnitPath.mockResolvedValue({
			id: 'path-1', unit_id: 'unit-1', version: 1, revision: 2, status: 'approved', generated_by: 'path_planner',
			merge_critic_results: [], prerequisite_risks: [], forward_verified: true,
			reaches_destination: true, completeness_note: null, approved_at: '2026-07-31T00:00:00Z',
			created_at: '2026-07-31T00:00:00Z', lessons: [lesson]
		});
		mocks.getPathHistory.mockResolvedValue([
			{ id: 'path-1', version: 1, revision: 2, status: 'approved', generated_by: 'path_planner', forward_verified: true, reaches_destination: true, risk_count: 0, approved_at: '2026-07-31T00:00:00Z', created_at: '2026-07-31T00:00:00Z' }
		]);
		mocks.getPathStatus.mockResolvedValue({
			path_version_id: 'path-1', path_revision: 2,
			counts: { unprepared: 0, awaiting_review: 1, generating: 0, ready: 0, warning: 0, failed: 0, skipped: 0, stale: 0 },
			lessons: [{ path_lesson_id: lesson.id, state: 'awaiting_review', generation_id: 'generation-1', warnings: [] }]
		});
		mocks.getTeachingSchedule.mockResolvedValue({
			path_version_id: 'path-1', path_revision: 2, schedule_revision: 1,
			feasibility: { estimated_minutes: 25, planned_minutes: 50, delta_minutes: 25, status: 'comfortable' },
			periods: [{
				id: 'period-1', title: 'Foundations', position: 1, planned_minutes: 50, teacher_note: null,
				lesson_ids: [lesson.id], lessons: [{ id: lesson.id, title: lesson.title, concept_id: lesson.concept_id, objective: lesson.objective, path_position: 0, estimated_minutes: 25 }],
				feasibility: { estimated_minutes: 25, planned_minutes: 50, delta_minutes: 25, status: 'comfortable' }
			}]
		});
		mocks.getUnitGroups.mockResolvedValue({
			unit_id: 'unit-1', groups_revision: 2,
			groups: [{ id: 'group-core', label: 'Core', profile: 'core', description: 'Main route.', toggle_profile: { support_level: 'medium', declared_toggles: [] }, voice: { register_name: 'balanced', tone: 'neutral', notation: null }, position: 1, revision: 1 }]
		});
		const canonical = {
			group_profile: 'core', support_level: 'medium',
			slots: [{ slot_id: 'check', role: 'check', purpose: 'Check', allowed_components: ['mcq'], locked: true, visual_required: false }],
			toggles_applied: [], warnings: [], structural_diff: [], blocking_issues: []
		};
		mocks.getLessonShape.mockResolvedValue({
			path_lesson_id: lesson.id, lesson_revision: 1, objective: lesson.objective,
			objective_hash: lesson.objective_hash, concept_id: lesson.concept_id, scope_exclusions: [],
			lesson_mode: 'first_exposure', misconception_count: 1,
			skeleton_id: 'factual-core', skeleton_version: 1, canonical,
			variants: [canonical], deviations: [], available_slots: ['orient', 'check'],
			blocking_issues: [], can_prepare: true
		});
		mocks.getPreparedLessonStatus.mockResolvedValue({
			path_lesson_id: lesson.id, lesson_revision: 1, generation_id: 'generation-1',
			generation_status: 'awaiting_review', workflow_stage: 'awaiting_review', objective_hash: 'hash',
			stale: false, can_prepare: false, can_regenerate: true
		});
	});
	afterEach(cleanup);

	it('shows the approved path, lesson shape, and durable review link', async () => {
		render(UnitPage);
		expect(await screen.findByRole('heading', { name: 'Photosynthesis' })).toBeTruthy();
		expect(await screen.findByText('Path v1 · approved')).toBeTruthy();
		expect(await screen.findByText('factual-core')).toBeTruthy();
		expect(screen.getByText('awaiting_review')).toBeTruthy();
		expect(screen.getByRole('heading', { name: 'Recoverable versions' })).toBeTruthy();
		expect(screen.getByText('Route verified')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Open review' }).getAttribute('href')).toBe(
			'/studio?generation_id=generation-1'
		);
	});

	it('replaces the review link with explicit recovery when preparation is stale', async () => {
		mocks.getPreparedLessonStatus.mockResolvedValue({
			path_lesson_id: lesson.id, lesson_revision: 2, generation_id: 'generation-1',
			generation_status: 'awaiting_review', workflow_stage: 'stale', objective_hash: 'changed',
			stale: true, can_prepare: false, can_regenerate: true
		});
		render(UnitPage);
		expect(await screen.findByRole('button', { name: 'Regenerate preparation' })).toBeTruthy();
		expect(screen.queryByRole('link', { name: 'Open review' })).toBeNull();
		expect(screen.getByLabelText('Regeneration reason')).toBeTruthy();
	});

	it('confirms a recoverable history restore before creating a new draft', async () => {
		mocks.getPathHistory.mockResolvedValue([
			{ id: 'path-1', version: 2, revision: 2, status: 'approved', generated_by: 'path_planner', forward_verified: true, reaches_destination: true, risk_count: 0, approved_at: '2026-07-31T00:00:00Z', created_at: '2026-07-31T00:00:00Z' },
			{ id: 'path-old', version: 1, revision: 3, status: 'superseded', generated_by: 'path_planner', forward_verified: true, reaches_destination: true, risk_count: 0, approved_at: null, created_at: '2026-07-30T00:00:00Z' }
		]);
		mocks.restorePathVersion.mockResolvedValue({});
		render(UnitPage);
		const restore = await screen.findByRole('button', { name: 'Restore' });
		await fireEvent.click(restore);
		expect(screen.getByRole('dialog', { name: 'Restore path v1' })).toBeTruthy();
		expect(screen.getByText('A new editable draft will be created. Nothing in history is deleted.')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));
		expect(mocks.restorePathVersion).toHaveBeenCalledWith(
			'unit-1', 'path-old', expect.objectContaining({ id: 'path-1', revision: 2 }),
			'Restore this version as a new editable draft.'
		);
	});

	it('shows schedule and group management as visible unit workspace views', async () => {
		render(UnitPage);
		await fireEvent.click(await screen.findByRole('button', { name: 'Schedule 1' }));
		expect(screen.getByRole('heading', { name: 'Group the route into periods' })).toBeTruthy();
		expect(screen.getByDisplayValue('Foundations')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Groups 1' }));
		expect(screen.getByRole('heading', { name: 'Declared structural variants' })).toBeTruthy();
		expect(screen.getByText(/one shared diagnostic item set/)).toBeTruthy();
	});
});
