// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '$lib/api/errors';

const mocks = vi.hoisted(() => ({
	getUnit: vi.fn(), getUnitPath: vi.fn(), getLessonShape: vi.fn(),
	getTeachingSchedule: vi.fn(), getUnitGroups: vi.fn(), saveTeachingSchedule: vi.fn(),
	listUnitResources: vi.fn(), previewUnitResource: vi.fn(), createUnitResource: vi.fn(),
	suggestTeachingSchedule: vi.fn(), saveUnitGroups: vi.fn(),
	getPathHistory: vi.fn(), getPathStatus: vi.fn(), getHistoricalPath: vi.fn(), restorePathVersion: vi.fn(),
	getPreparedLessonStatus: vi.fn(), approveUnitPath: vi.fn(), planUnitPath: vi.fn(),
	patchPathLesson: vi.fn(), mergePathLessons: vi.fn(), preparePathLesson: vi.fn(),
	regeneratePathLesson: vi.fn(), editUnitPathByChat: vi.fn()
}));

vi.mock('$app/state', () => ({ page: { params: { id: 'unit-1' } } }));
vi.mock('$lib/api/units', () => mocks);

import UnitPage from './+page.svelte';

const unit = {
	id: 'unit-1', title: 'Photosynthesis', topic: 'Plant food', subject: 'Science',
	grade_level: 'Grade 7', curriculum_context: null, class_notes: null,
	destination_objective: 'Explain how plants make food.', starting_knowledge: ['Plants are living.'],
	status: 'approved', active_path_version_id: 'path-1', groups_revision: 1
};
const lessonOne = {
	id: 'lesson-1', concept_id: 'concept-1', concept_slug: 'science.plant.inputs', title: 'Plant inputs',
	objective: 'Identify what plants need to make food.', objective_hash: 'hash-1', prerequisites: [],
	external_prerequisites: [], must_establish: ['plant inputs'], exclusions: [],
	primary_knowledge_type: 'factual', secondary_demand: null, knowledge_type_source: 'path_planner',
	merge_warning: false, position: 0, source: 'path_planner', teacher_edited: false,
	skipped: false, revision: 1, pack_id: null
};
const lessonTwo = {
	id: 'lesson-2', concept_id: 'concept-2', concept_slug: 'science.plant.outputs', title: 'Plant outputs',
	objective: 'Identify what plants produce.', objective_hash: 'hash-2', prerequisites: ['lesson-1'],
	external_prerequisites: [], must_establish: ['plant outputs'], exclusions: [],
	primary_knowledge_type: 'factual', secondary_demand: null, knowledge_type_source: 'path_planner',
	merge_warning: false, position: 1, source: 'path_planner', teacher_edited: false,
	skipped: false, revision: 1, pack_id: 'generation-1'
};

function buildPath(overrides: Record<string, unknown> = {}) {
	return {
		id: 'path-1', unit_id: 'unit-1', version: 1, revision: 2, status: 'approved', generated_by: 'path_planner',
		merge_critic_results: [], prerequisite_risks: [], forward_verified: true,
		reaches_destination: true, completeness_note: null,
		approved_at: '2026-07-31T00:00:00Z',
		created_at: '2026-07-31T00:00:00Z', lessons: [lessonOne, lessonTwo],
		...overrides
	};
}

describe('/units/[id]', () => {
	beforeEach(() => {
		Object.values(mocks).forEach((mock) => mock.mockReset());
		mocks.getUnit.mockResolvedValue(unit);
		mocks.getUnitPath.mockResolvedValue(buildPath());
		mocks.getPathHistory.mockResolvedValue([
			{ id: 'path-1', version: 1, revision: 2, status: 'approved', generated_by: 'path_planner', forward_verified: true, reaches_destination: true, risk_count: 0, approved_at: '2026-07-31T00:00:00Z', created_at: '2026-07-31T00:00:00Z' }
		]);
		mocks.getTeachingSchedule.mockResolvedValue({
			path_version_id: 'path-1', path_revision: 2, schedule_revision: 1,
			feasibility: { estimated_minutes: 25, planned_minutes: 50, delta_minutes: 25, status: 'comfortable' },
			periods: []
		});
		mocks.getUnitGroups.mockResolvedValue({
			unit_id: 'unit-1', groups_revision: 2,
			groups: [{ id: 'group-core', label: 'Core', profile: 'core', description: 'Main route.', toggle_profile: { support_level: 'medium', declared_toggles: [] }, voice: { register_name: 'balanced', tone: 'neutral', notation: null }, position: 1, revision: 1 }]
		});
		mocks.listUnitResources.mockResolvedValue([]);
		mocks.getLessonShape.mockResolvedValue({
			path_lesson_id: lessonOne.id, lesson_revision: 1, objective: lessonOne.objective,
			objective_hash: lessonOne.objective_hash, concept_id: lessonOne.concept_id, scope_exclusions: [],
			lesson_mode: 'first_exposure', misconception_count: 1,
			skeleton_id: 'factual-core', skeleton_version: 1, canonical: {
				group_profile: 'core', support_level: 'medium', slots: [], toggles_applied: [],
				warnings: [], structural_diff: [], blocking_issues: []
			},
			variants: [], deviations: [], available_slots: [],
			blocking_issues: [], can_prepare: true
		});
		mocks.getPreparedLessonStatus.mockResolvedValue({
			path_lesson_id: lessonOne.id, lesson_revision: 1, generation_id: null,
			generation_status: null, workflow_stage: 'unprepared', objective_hash: 'hash-1',
			stale: false, can_prepare: true, can_regenerate: false
		});
	});
	afterEach(cleanup);

	it('initial load fetches only unit and active path', async () => {
		render(UnitPage);
		expect(await screen.findByDisplayValue('Plant inputs')).toBeTruthy();
		expect(mocks.getUnit).toHaveBeenCalled();
		expect(mocks.getUnitPath).toHaveBeenCalled();
		expect(mocks.getUnitGroups).not.toHaveBeenCalled();
		expect(mocks.getTeachingSchedule).not.toHaveBeenCalled();
		expect(mocks.listUnitResources).not.toHaveBeenCalled();
		expect(mocks.getPathHistory).not.toHaveBeenCalled();
		expect(mocks.getPathStatus).not.toHaveBeenCalled();
		expect(mocks.getLessonShape).not.toHaveBeenCalled();
		expect(mocks.getPreparedLessonStatus).not.toHaveBeenCalled();
	});

	it('selecting a lesson does not fetch shape or preparation status', async () => {
		render(UnitPage);
		await screen.findByDisplayValue('Plant inputs');
		await fireEvent.click(screen.getByRole('button', { name: /Plant outputs/ }));
		expect(mocks.getLessonShape).not.toHaveBeenCalled();
		expect(mocks.getPreparedLessonStatus).not.toHaveBeenCalled();
		expect(screen.getByDisplayValue('Plant outputs')).toBeTruthy();
	});

	it('keeps lessons view when an optional tab endpoint fails', async () => {
		mocks.getUnitGroups.mockRejectedValue(new Error('groups unavailable'));
		render(UnitPage);
		await screen.findByDisplayValue('Plant inputs');
		await fireEvent.click(screen.getByRole('button', { name: 'Groups' }));
		expect(await screen.findByText('groups unavailable')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Lessons' }));
		expect(screen.getByDisplayValue('Plant inputs')).toBeTruthy();
	});

	it('lazy-loads history only when History tab is opened', async () => {
		render(UnitPage);
		await screen.findByDisplayValue('Plant inputs');
		expect(mocks.getPathHistory).not.toHaveBeenCalled();
		await fireEvent.click(screen.getByRole('button', { name: 'History' }));
		await waitFor(() => expect(mocks.getPathHistory).toHaveBeenCalled());
	});

	it('shows the numbered lesson list with dependency sentences', async () => {
		render(UnitPage);
		expect(await screen.findByDisplayValue('Plant inputs')).toBeTruthy();
		expect(screen.getByText('needs lesson 1')).toBeTruthy();
	});

	it('does not show merge questions or open assumptions in the default lessons view', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({
			status: 'draft',
			merge_critic_results: [{
				lesson_a: lessonOne.concept_slug, lesson_b: lessonTwo.concept_slug,
				verdict: 'merge_suggested', reason: 'they teach the same skill from two angles.',
				merged_objective: 'Explain what plants need and produce.', diagnostic_cost: null
			}],
		}));
		render(UnitPage);
		await screen.findByDisplayValue('Plant inputs');
		expect(screen.queryByText(/might work as one lesson/)).toBeNull();
		expect(screen.queryByText(/thing to confirm/)).toBeNull();
		expect(screen.getByRole('button', { name: 'Looks good — lock it in' }).hasAttribute('disabled')).toBe(false);
	});

	it('shows deterministic merge suggestions without blocking lock-in', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({
			status: 'draft',
			merge_critic_results: [{
				lesson_a: lessonOne.id,
				lesson_b: lessonTwo.id,
				verdict: 'review_suggested',
				reason: 'Lessons 1 and 2 cover similar ground and might work as one lesson.',
				source: 'deterministic'
			}]
		}));
		mocks.mergePathLessons.mockResolvedValue({
			path: buildPath({
				status: 'draft',
				lessons: [{ ...lessonOne, title: 'Plant inputs + Plant outputs', objective: 'Explain plant inputs and outputs together.' }]
			}),
			merged_lesson_id: lessonOne.id,
			source: 'teacher_merge'
		});
		render(UnitPage);
		await screen.findByText(/might work as one lesson/);
		expect(screen.getByRole('button', { name: 'Review merge' })).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Looks good — lock it in' }).hasAttribute('disabled')).toBe(false);
		await fireEvent.click(screen.getByRole('button', { name: 'Review merge' }));
		expect(mocks.mergePathLessons).not.toHaveBeenCalled();
		expect(screen.getByText(lessonOne.objective)).toBeTruthy();
		expect(screen.getByText(lessonTwo.objective)).toBeTruthy();
		const mergeButton = screen.getByRole('button', { name: 'Merge lessons' });
		expect(mergeButton.hasAttribute('disabled')).toBe(true);
		const objectiveField = screen.getByPlaceholderText(/Write one capability that genuinely covers both/);
		expect((objectiveField as HTMLTextAreaElement).value).toBe('');
		await fireEvent.input(objectiveField, {
			target: { value: 'Explain plant inputs and outputs together.' }
		});
		await waitFor(() => expect(mergeButton.hasAttribute('disabled')).toBe(false));
		await fireEvent.click(mergeButton);
		await waitFor(() => expect(mocks.mergePathLessons).toHaveBeenCalled());
		const payload = mocks.mergePathLessons.mock.calls[0][4];
		expect(payload.objective).toBe('Explain plant inputs and outputs together.');
		expect(payload.title).toBe('Plant inputs + Plant outputs');
		expect(payload.knowledge_type).toBe('factual');
		expect(payload.must_establish).toEqual(['plant inputs', 'plant outputs']);
	});

	it('requires knowledge type when merge sources differ', async () => {
		const conceptualTwo = { ...lessonTwo, primary_knowledge_type: 'conceptual' as const };
		mocks.getUnitPath.mockResolvedValue(buildPath({
			status: 'draft',
			lessons: [lessonOne, conceptualTwo],
			merge_critic_results: [{
				lesson_a: lessonOne.id,
				lesson_b: conceptualTwo.id,
				verdict: 'review_suggested',
				reason: 'These adjacent lessons overlap in what they establish.',
				source: 'deterministic'
			}]
		}));
		render(UnitPage);
		await fireEvent.click(await screen.findByRole('button', { name: 'Review merge' }));
		const mergeButton = screen.getByRole('button', { name: 'Merge lessons' });
		await fireEvent.input(screen.getByPlaceholderText(/Write one capability/), {
			target: { value: 'Explain both plant inputs and outputs.' }
		});
		expect(mergeButton.hasAttribute('disabled')).toBe(true);
		expect(mocks.mergePathLessons).not.toHaveBeenCalled();
		await fireEvent.change(screen.getByDisplayValue('Select a type'), { target: { value: 'conceptual' } });
		await waitFor(() => expect(mergeButton.hasAttribute('disabled')).toBe(false));
	});

	it('prepare does not preflight lesson shape', async () => {
		const locationStub = { href: '' };
		vi.stubGlobal('location', locationStub);
		mocks.preparePathLesson.mockResolvedValue({
			generation_id: 'gen-1',
			path_lesson_id: lessonOne.id,
			objective: lessonOne.objective,
			objective_hash: lessonOne.objective_hash,
			skeleton_id: 'factual-core',
			skeleton_version: 1,
			slots: [],
			section_roles: [],
			status: 'awaiting_review',
			reused: false
		});
		render(UnitPage);
		await screen.findByRole('button', { name: 'Prepare Lesson' });
		await fireEvent.click(screen.getByRole('button', { name: 'Prepare Lesson' }));
		await waitFor(() => expect(mocks.preparePathLesson).toHaveBeenCalled());
		expect(mocks.getLessonShape).not.toHaveBeenCalled();
		expect(mocks.preparePathLesson.mock.calls[0][4]).toEqual(['group-core']);
		expect(locationStub.href).toContain('gen-1');
		vi.unstubAllGlobals();
	});

	it('prepare still runs when groups load fails', async () => {
		vi.stubGlobal('location', { href: '' });
		mocks.getUnitGroups.mockRejectedValue(new Error('groups unavailable'));
		mocks.preparePathLesson.mockResolvedValue({
			generation_id: 'gen-2',
			path_lesson_id: lessonOne.id,
			objective: lessonOne.objective,
			objective_hash: lessonOne.objective_hash,
			skeleton_id: 'factual-core',
			skeleton_version: 1,
			slots: [],
			section_roles: [],
			status: 'awaiting_review',
			reused: false
		});
		render(UnitPage);
		await fireEvent.click(await screen.findByRole('button', { name: 'Prepare Lesson' }));
		await waitFor(() => expect(mocks.preparePathLesson).toHaveBeenCalled());
		expect(mocks.getLessonShape).not.toHaveBeenCalled();
		expect(mocks.preparePathLesson.mock.calls[0][4]).toEqual([]);
		vi.unstubAllGlobals();
	});

	it('edits the lessons from the chat input', async () => {
		mocks.editUnitPathByChat.mockResolvedValue({ path: buildPath(), validation_messages: [], note: 'Added a lesson on transpiration.' });
		render(UnitPage);
		const input = await screen.findByPlaceholderText(/Combine lessons 2 and 3/);
		await fireEvent.input(input, { target: { value: 'Add something about transpiration.' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		expect(mocks.editUnitPathByChat).toHaveBeenCalled();
	});

	it('locks in the path without open-assumption gates', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({ status: 'draft' }));
		mocks.approveUnitPath.mockResolvedValue(buildPath({ status: 'approved', approved_at: '2026-08-01T00:00:00Z' }));
		render(UnitPage);
		const lockButton = await screen.findByRole('button', { name: 'Looks good — lock it in' });
		expect(lockButton.hasAttribute('disabled')).toBe(false);
		await fireEvent.click(lockButton);
		expect(mocks.approveUnitPath).toHaveBeenCalled();
	});

	it('shows Prepare Lesson without requiring mount-time shape fetch', async () => {
		render(UnitPage);
		expect(await screen.findByRole('button', { name: 'Prepare Lesson' })).toBeTruthy();
		expect(mocks.getLessonShape).not.toHaveBeenCalled();
	});

	it('loads preparation status only when requested', async () => {
		mocks.getPreparedLessonStatus.mockResolvedValue({
			path_lesson_id: lessonOne.id, lesson_revision: 1, generation_id: 'generation-1',
			generation_status: 'awaiting_review', workflow_stage: 'awaiting_review', objective_hash: 'hash-1',
			stale: false, can_prepare: false, can_regenerate: true
		});
		render(UnitPage);
		await screen.findByRole('button', { name: 'Check preparation status' });
		await fireEvent.click(screen.getByRole('button', { name: 'Check preparation status' }));
		await waitFor(() => expect(mocks.getPreparedLessonStatus).toHaveBeenCalled());
		expect(await screen.findByRole('link', { name: 'Print' })).toBeTruthy();
	});
});
