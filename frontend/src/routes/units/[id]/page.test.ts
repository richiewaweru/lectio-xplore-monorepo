// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
	getUnit: vi.fn(), getUnitPath: vi.fn(), previewSkeleton: vi.fn(),
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
	status: 'approved', active_path_version_id: 'path-1'
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
			id: 'path-1', unit_id: 'unit-1', version: 1, status: 'approved', generated_by: 'path_planner',
			merge_critic_results: [], prerequisite_risks: [], forward_verified: true,
			reaches_destination: true, approved_at: '2026-07-31T00:00:00Z', lessons: [lesson]
		});
		mocks.previewSkeleton.mockResolvedValue({
			objective: lesson.objective, knowledge_type: 'factual', knowledge_type_source: 'provided',
			skeleton_id: 'factual-core', skeleton_version: 1,
			variants: [{ group_profile: 'core', support_level: 'medium', slots: [{ slot_id: 'check', role: 'check', purpose: 'Check', allowed_components: ['mcq'], locked: true, visual_required: false }], toggles_applied: [], warnings: [] }]
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
		expect(screen.getByText('Path v1 · approved')).toBeTruthy();
		expect(await screen.findByText('factual-core')).toBeTruthy();
		expect(screen.getByText('awaiting_review')).toBeTruthy();
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
});
