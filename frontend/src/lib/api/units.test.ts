import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client', () => ({ apiFetch: vi.fn() }));
vi.mock('./errors', () => ({ ensureOk: vi.fn().mockResolvedValue(undefined) }));

import { apiFetch } from './client';
import {
	decideShapeDeviation,
	getLessonShape,
	getMarksSummary,
	createUnitResource,
	previewUnitResource,
	planUnitPath,
	preparePathLesson,
	previewSkeleton,
	requestShapeDeviation,
	saveLessonActual,
	saveMarks,
	saveTeachingSchedule,
	saveUnitGroups,
	suggestTeachingSchedule
} from './units';
import type { PathLesson, UnitPath } from '$lib/types/units';

const activePath = { id: 'path-1', revision: 4 } as UnitPath;
const activeLesson = { id: 'lesson-1', revision: 2 } as PathLesson;

function ok(payload: unknown): Response {
	return new Response(JSON.stringify(payload), {
		status: 200,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('unit API helpers', () => {
	afterEach(() => vi.clearAllMocks());

	it('plans from persisted scope without count or duration targets', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ lessons: [] }));
		await planUnitPath('unit 1', {
			topic: 'Photosynthesis',
			subject: 'Science',
			grade_level: 'Grade 7',
			destination_objective: 'Explain photosynthesis.',
			starting_knowledge: ['Plants are living things.']
		});

		const [path, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(path).toBe('/api/v1/units/unit%201/path:plan');
		const body = JSON.parse(String((init as RequestInit).body));
		expect(body.lesson_count).toBeUndefined();
		expect(body.duration_minutes).toBeUndefined();
	});

	it('prepares the core path lesson through the explicit bridge', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ generation_id: 'generation-1' }));
		await preparePathLesson('unit-1', activePath, activeLesson, 'first_exposure');

		expect(apiFetch).toHaveBeenCalledWith(
			'/api/v1/units/unit-1/path/lessons/lesson-1:prepare',
			expect.objectContaining({
				method: 'POST',
				body: JSON.stringify({
					path_version_id: 'path-1', path_revision: 4, lesson_revision: 2,
					group_ids: [], lesson_mode: 'first_exposure'
				})
			})
		);
	});

	it('guards replanning with the active path revision', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ lessons: [] }));
		await planUnitPath('unit-1', {
			topic: 'Plants', subject: 'Science', grade_level: 'Grade 7',
			destination_objective: 'Explain photosynthesis.', starting_knowledge: []
		}, true, activePath);
		const [, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(JSON.parse(String((init as RequestInit).body))).toEqual(expect.objectContaining({
			path_version_id: 'path-1', path_revision: 4
		}));
	});

	it('previews all three declared group shapes without a generation call', async () => {
		vi.mocked(apiFetch).mockImplementation(async () => ok({ variants: [] }));
		await previewSkeleton('Explain photosynthesis.', 'first_exposure');

		const [, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(JSON.parse(String((init as RequestInit).body)).group_profiles).toEqual([
			'support',
			'core',
			'extension'
		]);
	});

	it('loads and explicitly approves path-owned shape deviations', async () => {
		vi.mocked(apiFetch).mockImplementation(async () => ok({ variants: [] }));
		await getLessonShape('unit-1', 'lesson-1', 'repair', 2);
		expect(vi.mocked(apiFetch).mock.calls[0][0]).toBe(
			'/api/v1/units/unit-1/path/lessons/lesson-1/shape?lesson_mode=repair&misconception_count=2'
		);

		await requestShapeDeviation('unit-1', activePath, activeLesson, {
			lesson_mode: 'repair', operation: 'replace', target_slot: 'explain',
			replacement_slot: 'model', reason: 'A worked scientific model is required.'
		});
		let [, init] = vi.mocked(apiFetch).mock.calls[1];
		expect(JSON.parse(String((init as RequestInit).body))).toEqual({
			path_version_id: 'path-1', path_revision: 4, lesson_revision: 2,
			lesson_mode: 'repair', operation: 'replace', target_slot: 'explain',
			replacement_slot: 'model', reason: 'A worked scientific model is required.'
		});

		await decideShapeDeviation('unit-1', activePath, activeLesson, 'dev 1', 'approve');
		[, init] = vi.mocked(apiFetch).mock.calls[2];
		expect(vi.mocked(apiFetch).mock.calls[2][0]).toContain('/dev%201:approve');
		expect(JSON.parse(String((init as RequestInit).body))).toEqual({
			path_version_id: 'path-1', path_revision: 4, lesson_revision: 2
		});
	});

	it('uses time only in schedule suggestion and guards schedule persistence', async () => {
		vi.mocked(apiFetch).mockImplementation(async () => ok({ periods: [] }));
		await suggestTeachingSchedule('unit-1', activePath, 3, 50);
		let [, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(JSON.parse(String((init as RequestInit).body))).toEqual({
			path_version_id: 'path-1', path_revision: 4, period_count: 3, minutes_per_period: 50
		});

		await saveTeachingSchedule('unit-1', activePath, {
			path_version_id: 'path-1', path_revision: 4, schedule_revision: 7,
			feasibility: { estimated_minutes: 40, planned_minutes: 50, delta_minutes: 10, status: 'tight' },
			periods: [{
				id: null, title: 'Foundations', position: 1, planned_minutes: 50, teacher_note: null,
				lesson_ids: ['lesson-1'], lessons: [],
				feasibility: { estimated_minutes: 40, planned_minutes: 50, delta_minutes: 10, status: 'tight' }
			}]
		});
		[, init] = vi.mocked(apiFetch).mock.calls[1];
		expect(JSON.parse(String((init as RequestInit).body))).toEqual({
			path_version_id: 'path-1', path_revision: 4, schedule_revision: 7,
			periods: [{ id: null, title: 'Foundations', lesson_ids: ['lesson-1'], planned_minutes: 50, teacher_note: null }]
		});
	});

	it('persists only group declarations, leaving structural toggles server-owned', async () => {
		vi.mocked(apiFetch).mockResolvedValue(ok({ groups: [] }));
		await saveUnitGroups('unit-1', { unit_id: 'unit-1', groups_revision: 3, groups: [] }, [{
			label: 'Support', profile: 'support', description: 'More modelling.',
			voice: { register_name: 'simple', tone: 'encouraging', notation: null }
		}]);
		const [, init] = vi.mocked(apiFetch).mock.calls[0];
		const body = JSON.parse(String((init as RequestInit).body));
		expect(body.groups_revision).toBe(3);
		expect(body.groups[0].profile).toBe('support');
		expect(body.groups[0].toggle_profile).toBeUndefined();
	});

	it('previews and creates deterministic projections with path guards', async () => {
		vi.mocked(apiFetch).mockImplementation(async () => ok({ projection: 'revision_sheet' }));
		const input = {
			projection: 'revision_sheet' as const,
			path_lesson_ids: ['lesson-1'], period_ids: [], group_ids: ['group-core'],
			component_refs: ['generation-1:intro'], item_ids: [],
			include_keys: false, include_support_notes: false
		};
		await previewUnitResource('unit-1', activePath, input);
		await createUnitResource('unit-1', activePath, input);

		expect(vi.mocked(apiFetch).mock.calls.map(([url]) => url)).toEqual([
			'/api/v1/units/unit-1/compose:preview', '/api/v1/units/unit-1/compose'
		]);
		for (const [, init] of vi.mocked(apiFetch).mock.calls) {
			expect(JSON.parse(String((init as RequestInit).body))).toEqual(expect.objectContaining({
				path_version_id: 'path-1', path_revision: 4, projection: 'revision_sheet',
				component_refs: ['generation-1:intro']
			}));
		}
	});

	it('saves guarded actual revisions and aggregate option counts', async () => {
		vi.mocked(apiFetch).mockImplementation(async () => ok({ revision: 1 }));
		await saveLessonActual('unit-1', activePath, activeLesson, {
			actual_revision: 0, status: 'partial', pace: 'slower',
			established_concepts: ['Leaves make food.'],
			unresolved_misconceptions: ['soil-food'], anchor_used: null, teacher_note: 'Revisit.'
		});
		await getMarksSummary('unit-1', 'lesson-1', 'group core');
		await saveMarks('unit-1', activePath, activeLesson, {
			marks_revision: 0, group_id: 'group core',
			items: [{ item_id: 'item-1', option_counts: { A: 9, B: 2 } }]
		});

		let [, init] = vi.mocked(apiFetch).mock.calls[0];
		expect(JSON.parse(String((init as RequestInit).body))).toEqual(expect.objectContaining({
			path_version_id: 'path-1', path_revision: 4, lesson_revision: 2,
			actual_revision: 0, status: 'partial'
		}));
		expect(vi.mocked(apiFetch).mock.calls[1][0]).toContain('group_id=group%20core');
		[, init] = vi.mocked(apiFetch).mock.calls[2];
		expect(JSON.parse(String((init as RequestInit).body))).toEqual({
			path_version_id: 'path-1', path_revision: 4, lesson_revision: 2,
			marks_revision: 0, group_id: 'group core',
			items: [{ item_id: 'item-1', option_counts: { A: 9, B: 2 } }]
		});
	});
});
