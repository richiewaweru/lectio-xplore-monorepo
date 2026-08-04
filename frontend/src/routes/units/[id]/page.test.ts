// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
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
	regeneratePathLesson: vi.fn(), editUnitPathByChat: vi.fn(), resolvePathAssumption: vi.fn()
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
const lessonOne = {
	id: 'lesson-1', concept_id: 'concept-1', concept_slug: 'plant.inputs', title: 'Plant inputs',
	objective: 'Identify what plants need to make food.', objective_hash: 'hash-1', prerequisites: [],
	external_prerequisites: [], must_establish: ['plant inputs'], exclusions: [],
	primary_knowledge_type: 'factual', secondary_demand: null, knowledge_type_source: 'path_planner',
	merge_warning: false, position: 0, source: 'path_planner', teacher_edited: false,
	skipped: false, revision: 1, pack_id: null
};
const lessonTwo = {
	id: 'lesson-2', concept_id: 'concept-2', concept_slug: 'plant.outputs', title: 'Plant outputs',
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
		reaches_destination: true, completeness_note: null, open_assumptions: [],
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
		mocks.getPathStatus.mockResolvedValue({
			path_version_id: 'path-1', path_revision: 2,
			counts: { unprepared: 1, awaiting_review: 1, generating: 0, ready: 0, warning: 0, failed: 0, skipped: 0, stale: 0 },
			lessons: [{ path_lesson_id: lessonTwo.id, state: 'awaiting_review', generation_id: 'generation-1', warnings: [] }]
		});
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
		const canonical = {
			group_profile: 'core', support_level: 'medium',
			slots: [{ slot_id: 'check', role: 'check', purpose: 'Check', allowed_components: ['mcq'], locked: true, visual_required: false }],
			toggles_applied: [], warnings: [], structural_diff: [], blocking_issues: []
		};
		mocks.getLessonShape.mockResolvedValue({
			path_lesson_id: lessonOne.id, lesson_revision: 1, objective: lessonOne.objective,
			objective_hash: lessonOne.objective_hash, concept_id: lessonOne.concept_id, scope_exclusions: [],
			lesson_mode: 'first_exposure', misconception_count: 1,
			skeleton_id: 'factual-core', skeleton_version: 1, canonical,
			variants: [canonical], deviations: [], available_slots: ['orient', 'check'],
			blocking_issues: [], can_prepare: true
		});
		mocks.getPreparedLessonStatus.mockResolvedValue({
			path_lesson_id: lessonOne.id, lesson_revision: 1, generation_id: null,
			generation_status: null, workflow_stage: 'unprepared', objective_hash: 'hash-1',
			stale: false, can_prepare: true, can_regenerate: false
		});
	});
	afterEach(cleanup);

	it('shows the numbered lesson list with plain-language dependency sentences', async () => {
		render(UnitPage);
		expect(await screen.findByText('Plant inputs')).toBeTruthy();
		expect(screen.getByText('Plant outputs')).toBeTruthy();
		expect(screen.getByText('needs lesson 1')).toBeTruthy();
		expect(screen.queryByText(/concept path/i)).toBeNull();
	});

	it('shows an inline merge question and combines lessons when the teacher agrees', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({
			merge_critic_results: [{
				lesson_a: lessonOne.concept_slug, lesson_b: lessonTwo.concept_slug,
				verdict: 'merge_suggested', reason: 'they teach the same skill from two angles.',
				merged_objective: 'Explain what plants need and produce.', diagnostic_cost: null
			}]
		}));
		mocks.mergePathLessons.mockResolvedValue({});
		render(UnitPage);

		expect(
			await screen.findByText('Lessons 1 and 2 might work as one lesson — they teach the same skill from two angles.')
		).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Combine' }));
		expect(mocks.mergePathLessons).toHaveBeenCalled();
	});

	it('dismisses a merge question when the teacher keeps lessons apart', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({
			merge_critic_results: [{
				lesson_a: lessonOne.concept_slug, lesson_b: lessonTwo.concept_slug,
				verdict: 'teacher_decision', reason: 'they could go either way.',
				merged_objective: null, diagnostic_cost: null
			}]
		}));
		render(UnitPage);
		await screen.findByText(/might work as one lesson/);
		await fireEvent.click(screen.getByRole('button', { name: 'Keep apart' }));
		expect(screen.queryByText(/might work as one lesson/)).toBeNull();
		expect(mocks.mergePathLessons).not.toHaveBeenCalled();
	});

	it('edits the lessons from the chat input', async () => {
		mocks.editUnitPathByChat.mockResolvedValue({ ...buildPath(), note: 'Added a lesson on transpiration.' });
		render(UnitPage);
		const input = await screen.findByPlaceholderText(/Combine lessons 2 and 3/);
		await fireEvent.input(input, { target: { value: 'Add something about transpiration.' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		expect(mocks.editUnitPathByChat).toHaveBeenCalledWith(
			'unit-1', expect.objectContaining({ id: 'path-1' }), 'Add something about transpiration.'
		);
		expect(await screen.findByText('Added a lesson on transpiration.')).toBeTruthy();
	});

	it('shows a friendly disabled message when chat editing is not available yet', async () => {
		mocks.editUnitPathByChat.mockRejectedValue(new ApiError(404, 'Not found'));
		render(UnitPage);
		const input = await screen.findByPlaceholderText(/Combine lessons 2 and 3/);
		await fireEvent.input(input, { target: { value: 'Add something about transpiration.' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Send' }));
		expect(
			await screen.findByText("Editing lessons by chat isn't available yet — use the lesson tools above for now.")
		).toBeTruthy();
	});

	it('locks in the path once it reaches the destination with no open risks', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({ status: 'draft' }));
		mocks.approveUnitPath.mockResolvedValue(buildPath({ status: 'approved', approved_at: '2026-08-01T00:00:00Z' }));
		render(UnitPage);
		const lockButton = await screen.findByRole('button', { name: 'Looks good — lock it in' });
		expect(lockButton.hasAttribute('disabled')).toBe(false);
		await fireEvent.click(lockButton);
		expect(mocks.approveUnitPath).toHaveBeenCalled();
	});

	it('explains in plain language why the route cannot be locked in yet', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({ status: 'draft', reaches_destination: false }));
		render(UnitPage);
		await screen.findByRole('button', { name: 'Looks good — lock it in' });
		expect(screen.getByText("This route doesn't reach the destination yet.")).toBeTruthy();
	});

	it('blocks lock-in and asks the teacher to confirm open assumptions', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({
			status: 'draft',
			open_assumptions: [{ claimed: 'multiply any two fractions', needed_by: lessonOne.concept_slug }]
		}));
		mocks.resolvePathAssumption.mockResolvedValue(buildPath({
			status: 'draft',
			revision: 3,
			open_assumptions: []
		}));
		mocks.getUnit.mockResolvedValue({
			...unit,
			starting_knowledge: [...unit.starting_knowledge, 'multiply any two fractions']
		});
		render(UnitPage);

		expect(await screen.findByText(/1 thing to confirm/)).toBeTruthy();
		expect(screen.getByText('multiply any two fractions')).toBeTruthy();
		expect(screen.getByText('Needed for: Plant inputs')).toBeTruthy();
		const lockButton = screen.getByRole('button', { name: 'Looks good — lock it in' });
		expect(lockButton.hasAttribute('disabled')).toBe(true);
		expect(screen.getByText('Confirm what the class already knows before locking it in.')).toBeTruthy();

		await fireEvent.click(screen.getByRole('button', { name: 'Yes, they know this' }));
		expect(mocks.resolvePathAssumption).toHaveBeenCalledWith(
			'unit-1',
			expect.objectContaining({ id: 'path-1', revision: 2 }),
			{ claimed: 'multiply any two fractions', decision: 'known' }
		);
		expect(await screen.findByRole('button', { name: 'Looks good — lock it in' })).toBeTruthy();
		expect(screen.queryByText(/thing to confirm/)).toBeNull();
		expect(screen.getByRole('button', { name: 'Looks good — lock it in' }).hasAttribute('disabled')).toBe(false);
	});

	it('records a teach decision for an open assumption', async () => {
		mocks.getUnitPath.mockResolvedValue(buildPath({
			status: 'draft',
			open_assumptions: [{ claimed: 'multiply any two fractions', needed_by: lessonTwo.concept_slug }]
		}));
		mocks.resolvePathAssumption.mockResolvedValue(buildPath({
			status: 'draft',
			revision: 3,
			open_assumptions: [],
			reaches_destination: false,
			prerequisite_risks: [{ missing: 'multiply any two fractions', needed_by: lessonTwo.concept_slug, note: 'teacher declined' }]
		}));
		render(UnitPage);
		await screen.findByText(/1 thing to confirm/);
		await fireEvent.click(screen.getByRole('button', { name: 'No, teach it' }));
		expect(mocks.resolvePathAssumption).toHaveBeenCalledWith(
			'unit-1',
			expect.objectContaining({ id: 'path-1' }),
			{ claimed: 'multiply any two fractions', decision: 'teach' }
		);
		expect(await screen.findByText("Something in this route relies on knowledge that isn't taught yet — fix that before locking it in.")).toBeTruthy();
	});

	it('shows a plain-language prompt to make the lesson, with no knowledge-type controls', async () => {
		render(UnitPage);
		expect(await screen.findByRole('button', { name: 'Make the lesson' })).toBeTruthy();
		expect(screen.queryByText(/knowledge type/i)).toBeNull();
		expect(screen.queryByText(/merge critic/i)).toBeNull();
		expect(screen.queryByText(/forward verified/i)).toBeNull();
		expect(screen.queryByText(/prerequisite risk/i)).toBeNull();
	});

	it('offers Print and Make versions for my groups once a lesson is prepared', async () => {
		mocks.getPreparedLessonStatus.mockResolvedValue({
			path_lesson_id: lessonOne.id, lesson_revision: 1, generation_id: 'generation-1',
			generation_status: 'awaiting_review', workflow_stage: 'awaiting_review', objective_hash: 'hash-1',
			stale: false, can_prepare: false, can_regenerate: true
		});
		render(UnitPage);
		expect(await screen.findByRole('link', { name: 'Print' })).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'Make versions for my groups' }));
		expect(await screen.findByRole('heading', { name: 'Make versions for my groups' })).toBeTruthy();
		expect(
			screen.getByText('All versions share the same quiz, so you can compare the whole class fairly.')
		).toBeTruthy();
	});
});
