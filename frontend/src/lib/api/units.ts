import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';
import type {
	KnowledgeType,
	LessonMode,
	PathPlannerInput,
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

export function planUnitPath(unitId: string, input: PathPlannerInput, replan = false): Promise<UnitPath> {
	const action = replan ? 'replan' : 'plan';
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path:${action}`, 'Could not plan the concept path.', {
		method: 'POST',
		headers: jsonHeaders,
		body: JSON.stringify(input)
	});
}

export function approveUnitPath(unitId: string): Promise<UnitPath> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path:approve`, 'Could not approve the concept path.', { method: 'POST' });
}

export function patchPathLesson(
	unitId: string,
	lessonId: string,
	input: {
		title?: string;
		objective?: string;
		exclusions?: string[];
		must_establish?: string[];
		primary_knowledge_type?: KnowledgeType;
		secondary_demand?: KnowledgeType | null;
	}
): Promise<{ id: string; objective: string; revision: number }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}`,
		'Could not update the path lesson.',
		{ method: 'PATCH', headers: jsonHeaders, body: JSON.stringify(input) }
	);
}

export function skipPathLesson(unitId: string, lessonId: string): Promise<{ id: string; skipped: boolean; revision: number }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}:skip`,
		'Could not skip the path lesson.',
		{ method: 'POST' }
	);
}

export function reorderPathLessons(unitId: string, lessonIds: string[]): Promise<{ lesson_ids: string[] }> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons:reorder`, 'Could not reorder the concept path.', {
		method: 'POST', headers: jsonHeaders, body: JSON.stringify({ lesson_ids: lessonIds })
	});
}

export function splitPathLesson(
	unitId: string,
	lessonId: string,
	parts: Array<{
		concept_candidate: { slug: string; title: string };
		objective: string;
		must_establish: string[];
		exclusions: string[];
		primary_knowledge_type: KnowledgeType;
		secondary_demand: KnowledgeType | null;
	}>
): Promise<{ source_lesson_id: string; part_ids: string[] }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}:split`,
		'Could not split the path lesson.',
		{ method: 'POST', headers: jsonHeaders, body: JSON.stringify({ parts }) }
	);
}

export function mergePathLessons(
	unitId: string,
	lessonIds: string[],
	merged: {
		concept_candidate: { slug: string; title: string };
		objective: string;
		must_establish: string[];
		exclusions: string[];
		primary_knowledge_type: KnowledgeType;
		secondary_demand: KnowledgeType | null;
	}
): Promise<{ merged_lesson_id: string; source: string }> {
	return jsonRequest(`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons:merge`, 'Could not merge the path lessons.', {
		method: 'POST', headers: jsonHeaders, body: JSON.stringify({ lesson_ids: lessonIds, merged })
	});
}

export function preparePathLesson(unitId: string, lessonId: string, lessonMode: LessonMode): Promise<PreparedLesson> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}:prepare`,
		'Could not prepare the lesson.',
		{ method: 'POST', headers: jsonHeaders, body: JSON.stringify({ group_ids: [], lesson_mode: lessonMode }) }
	);
}

export function regeneratePathLesson(
	unitId: string,
	lessonId: string,
	lessonMode: LessonMode,
	reason: string
): Promise<PreparedLesson & { regeneration_reason: string }> {
	return jsonRequest(
		`/api/v1/units/${encodeURIComponent(unitId)}/path/lessons/${encodeURIComponent(lessonId)}:regenerate`,
		'Could not regenerate the lesson preparation.',
		{
			method: 'POST',
			headers: jsonHeaders,
			body: JSON.stringify({ group_ids: [], lesson_mode: lessonMode, reason })
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
