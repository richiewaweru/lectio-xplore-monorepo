import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';
import type {
	KnowledgeType,
	LessonMode,
	PathLesson,
	PathPlannerInput,
	PathStatusAggregate,
	PathVersionSummary,
	PreparedLesson,
	PreparedLessonStatus,
	SkeletonPreview,
	Unit,
	UnitCreateInput,
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

export function getUnitPath(unitId: string): Promise<UnitPath> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path`, 'Could not load the concept path.');
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
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path:${action}`, 'Could not plan the concept path.', {
		method: 'POST',
		headers: jsonHeaders,
		body: JSON.stringify(replan ? { ...input, path_version_id: active?.id, path_revision: active?.revision } : input)
	});
}

export function approveUnitPath(unitId: string, path: UnitPath): Promise<UnitPath> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path:approve`, 'Could not approve the concept path.', {
		method: 'POST', headers: jsonHeaders,
		body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision })
	});
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

export function preparePathLesson(unitId: string, path: UnitPath, lesson: PathLesson, lessonMode: LessonMode): Promise<PreparedLesson> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}:prepare`,
		'Could not prepare the lesson.',
		{
			method: 'POST', headers: jsonHeaders,
			body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision, group_ids: [], lesson_mode: lessonMode })
		}
	);
}

export function regeneratePathLesson(
	unitId: string,
	path: UnitPath,
	lesson: PathLesson,
	lessonMode: LessonMode,
	reason: string
): Promise<PreparedLesson & { regeneration_reason: string }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lesson.id)}:regenerate`,
		'Could not regenerate the lesson preparation.',
		{
			method: 'POST',
			headers: jsonHeaders,
			body: JSON.stringify({ path_version_id: path.id, path_revision: path.revision, lesson_revision: lesson.revision, group_ids: [], lesson_mode: lessonMode, reason })
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
