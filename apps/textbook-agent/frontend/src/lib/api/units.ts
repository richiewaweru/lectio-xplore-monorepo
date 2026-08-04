import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';
import type {
	ConstructorReadback,
	ConstructorReadbackInput,
	KnowledgeType,
	LegacyUnitWrapper,
	LessonActual,
	LessonActualStatus,
	LessonShapeDeviation,
	LessonShapePreview,
	LessonMode,
	LessonPace,
	MarksSummary,
	PathEditChatResult,
	PathLesson,
	PathPlannerInput,
	PathStatusAggregate,
	PathVersionSummary,
	PreparedLesson,
	PreparedLessonStatus,
	ResourceComposeInput,
	ResourceComposition,
	SkeletonPreview,
	TeachingSchedule,
	Unit,
	UnitCreateInput,
	UnitGroup,
	UnitGroups,
	UnitPath
} from '$lib/types/units';

const jsonHeaders = { 'Content-Type': 'application/json' };

async function jsonRequest<T>(path: string, fallback: string, init?: RequestInit): Promise<T> {
	const response = await apiFetch(path, init);
	await ensureOk(response, fallback);
	return response.json() as Promise<T>;
}

export function listUnits(): Promise<Unit[]> {
	return jsonRequest('/api/v1/units', 'Could not load units.');
}

export function listLegacyUnitWrappers(): Promise<LegacyUnitWrapper[]> {
	return jsonRequest('/api/v1/legacy-units', 'Could not load legacy unit wrappers.');
}

export function getLegacyUnitWrapper(packId: string): Promise<LegacyUnitWrapper> {
	return jsonRequest(`/api/v1/legacy-units/${encodeURIComponent(packId)}`, 'Could not load this legacy unit.');
}

export function getUnit(unitId: string): Promise<Unit> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}`, 'Could not load this unit.');
}

export function createUnit(input: UnitCreateInput): Promise<Unit> {
	return jsonRequest('/api/v1/units', 'Could not create the unit.', {
		method: 'POST',
		headers: jsonHeaders,
		body: JSON.stringify(input)
	});
}

export function constructorReadback(input: ConstructorReadbackInput): Promise<ConstructorReadback> {
	return jsonRequest('/api/v1/units/constructor/readback', "Could not read back what you're teaching.", {
		method: 'POST',
		headers: jsonHeaders,
		body: JSON.stringify(input)
	});
}

export function getUnitPath(unitId: string): Promise<UnitPath> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path`, 'Could not load the lessons.');
}

export function getPathHistory(unitId: string): Promise<PathVersionSummary[]> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/versions`, 'Could not load path history.');
}

export function getHistoricalPath(unitId: string, versionId: string): Promise<UnitPath> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/versions/${encodeURIComponent(versionId)}`,
		'Could not load this path version.'
	);
}

export function getPathStatus(unitId: string): Promise<PathStatusAggregate> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/status`, 'Could not load path status.');
}

export function getTeachingSchedule(unitId: string): Promise<TeachingSchedule> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/schedule`, 'Could not load the teaching schedule.');
}

export function suggestTeachingSchedule(
	unitId: string,
	path: UnitPath,
	periodCount: number,
	minutesPerPeriod: number
): Promise<TeachingSchedule> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/schedule:suggest`, 'Could not suggest a teaching schedule.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({
			path_version_id: path.id, path_revision: path.revision,
			period_count: periodCount, minutes_per_period: minutesPerPeriod
		})
	});
}

export function saveTeachingSchedule(unitId: string, path: UnitPath, schedule: TeachingSchedule): Promise<TeachingSchedule> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/schedule`, 'Could not save the teaching schedule.', {
		method: 'PUT', headers: jsonHeaders,
		body: JSON.stringify({
			path_version_id: path.id, path_revision: path.revision,
			schedule_revision: schedule.schedule_revision,
			periods: schedule.periods.map((period) => ({
				id: period.id, title: period.title, lesson_ids: period.lesson_ids,
				planned_minutes: period.planned_minutes, teacher_note: period.teacher_note
			}))
		})
	});
}

export function getUnitGroups(unitId: string): Promise<UnitGroups> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/groups`, 'Could not load unit groups.');
}

export function saveUnitGroups(unitId: string, current: UnitGroups, groups: Array<{
	id?: string;
	label: string;
	profile: UnitGroup['profile'];
	description: string;
	voice: UnitGroup['voice'];
}>): Promise<UnitGroups> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/groups`, 'Could not save unit groups.', {
		method: 'PUT', headers: jsonHeaders,
		body: JSON.stringify({ groups_revision: current.groups_revision, groups })
	});
}

export function restorePathVersion(unitId: string, sourceVersionId: string, active: UnitPath, reason: string): Promise<UnitPath> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/versions/${encodeURIComponent(sourceVersionId)}:restore`,
		'Could not restore this path version.',
		{
			method: 'POST', headers: jsonHeaders,
			body: JSON.stringify({ path_version_id: active.id, path_revision: active.revision, reason })
		}
	);
}

export function planUnitPath(unitId: string, input: PathPlannerInput, replan = false, active?: UnitPath): Promise<UnitPath> {
	const action = replan ? 'replan' : 'plan';
	if (replan && !active) throw new Error('Replanning requires the active path revision.');
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path:${action}`, 'Could not plan the lessons.', {
		method: 'POST',
		headers: jsonHeaders,
		body: JSON.stringify(replan ? { ...input, path_version_id: active?.id, path_revision: active?.revision } : input)
	});
}

export function editUnitPathByChat(unitId: string, path: UnitPath, message: string): Promise<PathEditChatResult> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path:edit-chat`, 'Could not update the lessons from that message.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({ message, path_version_id: path.id, path_revision: path.revision })
	});
}

export function approveUnitPath(unitId: string, path: UnitPath): Promise<UnitPath> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path:approve`, 'Could not lock in the lessons.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision })
	});
}

export function resolvePathAssumption(
	unitId: string,
	path: UnitPath,
	input: { claimed: string; decision: 'known' | 'teach' }
): Promise<UnitPath> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/assumptions/resolve`,
		'Could not confirm that prior knowledge.',
		{
			method: 'POST',
			headers: jsonHeaders,
			body: JSON.stringify({
				path_version_id: path.id,
				path_revision: path.revision,
				claimed: input.claimed,
				decision: input.decision
			})
		}
	);
}

export function patchPathLesson(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	input: {
		title?: string;
		objective?: string;
		exclusions?: string[];
		must_establish?: string[];
		primary_knowledge_type?: KnowledgeType;
		secondary_demand?: KnowledgeType | null;
	}
): Promise<{ id: string; objective: string; revision: number; path_version_id: string; path_revision: number }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}`,
		'Could not update the path lesson.',
		{
			method: 'PATCH', headers: jsonHeaders,
			body: JSON.stringify({
				...input, path_version_id: path.id, path_revision: path.revision,
				lesson_revision: lesson.revision
			})
		}
	);
}

export function skipPathLesson(unitId: string, path: UnitPath, lesson: PathLesson): Promise<UnitPath> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}:skip`,
		'Could not skip the path lesson.',
		{
			method: 'POST', headers: jsonHeaders,
			body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision })
		}
	);
}

export function reorderPathLessons(unitId: string, path: UnitPath, lessonIds: string[]): Promise<{ lesson_ids: string[]; path: UnitPath }> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons:reorder`, 'Could not reorder the concept path.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_ids: lessonIds })
	});
}

export function splitPathLesson(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	parts: Array<{
		concept_candidate: { slug: string; title: string };
		objective: string;
		must_establish: string[];
		exclusions: string[];
		primary_knowledge_type: KnowledgeType;
		secondary_demand: KnowledgeType | null;
	}>
): Promise<{ path: UnitPath; source_lesson_id: string; part_ids: string[] }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}:split`,
		'Could not split the path lesson.',
		{
			method: 'POST', headers: jsonHeaders,
			body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision, parts })
		}
	);
}

export function mergePathLessons(
	unitId: string,
	path: UnitPath,
	lessons: PathLesson[],
	lessonIds: string[],
	merged: {
		concept_candidate: { slug: string; title: string };
		objective: string;
		must_establish: string[];
		exclusions: string[];
		primary_knowledge_type: KnowledgeType;
		secondary_demand: KnowledgeType | null;
	}
): Promise<{ path: UnitPath; merged_lesson_id: string; source: string }> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons:merge`, 'Could not merge the path lessons.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({
			path_version_id: path.id, path_revision: path.revision, lesson_ids: lessonIds,
			lesson_revisions: Object.fromEntries(lessons.map((lesson) => [lesson.id, lesson.revision])), merged
		})
	});
}

export function preparePathLesson(unitId: string, path: UnitPath, lesson: PathLesson, lessonMode: LessonMode, groupIds: string[] = []): Promise<PreparedLesson> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}:prepare`,
		'Could not prepare the lesson.',
		{
			method: 'POST', headers: jsonHeaders,
			body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision, group_ids: groupIds, lesson_mode: lessonMode })
		}
	);
}

export function regeneratePathLesson(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	lessonMode: LessonMode,
	reason: string,
	groupIds: string[] = []
): Promise<PreparedLesson & { regeneration_reason: string }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}:regenerate`,
		'Could not regenerate the lesson preparation.',
		{
			method: 'POST',
			headers: jsonHeaders,
			body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision, group_ids: groupIds, lesson_mode: lessonMode, reason })
		}
	);
}

export function getPreparedLessonStatus(unitId: string, lessonId: string): Promise<PreparedLessonStatus> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}/status`,
		'Could not load lesson preparation status.'
	);
}

export function previewSkeleton(objective: string, lessonMode: LessonMode): Promise<SkeletonPreview> {
	return jsonRequest('/api/v1/skeletons:preview', 'Could not preview the lesson shape.', {
		method: 'POST',
		headers: jsonHeaders,
		body: JSON.stringify({
			objective,
			lesson_mode: lessonMode,
			misconception_count: 0,
			group_profiles: ['support', 'core', 'extension']
		})
	});
}

export function getLessonShape(
	unitId: string,
	lessonId: string,
	lessonMode: LessonMode,
	misconceptionCount: number
): Promise<LessonShapePreview> {
	const query = new URLSearchParams({
		lesson_mode: lessonMode,
		misconception_count: String(misconceptionCount)
	});
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}/shape?${query}`,
		'Could not load the controlled lesson shape.'
	);
}

export function requestShapeDeviation(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	input: {
		lesson_mode: LessonMode;
		operation: 'insert' | 'remove' | 'replace' | 'reorder';
		target_slot: string;
		replacement_slot: string | null;
		reason: string;
	}
): Promise<LessonShapeDeviation> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}/shape/deviations`,
		'Could not request the shape deviation.',
		{
			method: 'POST', headers: jsonHeaders,
			body: JSON.stringify({
				path_version_id: path.id, path_revision: path.revision,
				lesson_revision: lesson.revision, ...input
			})
		}
	);
}

export function decideShapeDeviation(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	deviationId: string,
	decision: 'approve' | 'reject'
): Promise<LessonShapeDeviation & { lesson_revision: number }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}/shape/deviations/${encodeURIComponent(deviationId)}:${decision}`,
		`Could not ${decision} the shape deviation.`,
		{
			method: 'POST', headers: jsonHeaders,
			body: JSON.stringify({
				path_version_id: path.id, path_revision: path.revision,
				lesson_revision: lesson.revision
			})
		}
	);
}

function guardedCompositionInput(path: UnitPath, input: ResourceComposeInput) {
	return { path_version_id: path.id, path_revision: path.revision, ...input };
}

export function previewUnitResource(
	unitId: string,
	path: UnitPath,
	input: ResourceComposeInput
): Promise<ResourceComposition> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/compose:preview`, 'Could not preview the resource projection.', {
		method: 'POST', headers: jsonHeaders, body: JSON.stringify(guardedCompositionInput(path, input))
	});
}

export function createUnitResource(
	unitId: string,
	path: UnitPath,
	input: ResourceComposeInput
): Promise<ResourceComposition> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/compose`, 'Could not create the resource projection.', {
		method: 'POST', headers: jsonHeaders, body: JSON.stringify(guardedCompositionInput(path, input))
	});
}

export function listUnitResources(unitId: string): Promise<ResourceComposition[]> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/compositions`, 'Could not load resource projections.');
}

export function getUnitResource(unitId: string, compositionId: string): Promise<ResourceComposition> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/compositions/${encodeURIComponent(compositionId)}`, 'Could not load this resource projection.');
}

export function getLessonActual(unitId: string, lessonId: string): Promise<LessonActual | null> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}/actual`, 'Could not load the lesson actual.');
}

export function saveLessonActual(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	input: {
		actual_revision: number;
		status: LessonActualStatus;
		pace: LessonPace;
		established_concepts: string[];
		unresolved_misconceptions: string[];
		anchor_used: string | null;
		teacher_note: string | null;
	}
): Promise<LessonActual> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}/actual`, 'Could not save the lesson actual.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision, ...input })
	});
}

export function getMarksSummary(unitId: string, lessonId: string, groupId: string | null): Promise<MarksSummary> {
	const query = groupId ? `?group_id=${encodeURIComponent(groupId)}` : '';
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}/marks-summary${query}`, 'Could not load aggregate marks.');
}

export function saveMarks(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	input: { marks_revision: number; group_id: string | null; items: Array<{ item_id: string; option_counts: Record<string, number> }> }
): Promise<MarksSummary> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}/marks`, 'Could not save aggregate marks.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision, ...input })
	});
}
