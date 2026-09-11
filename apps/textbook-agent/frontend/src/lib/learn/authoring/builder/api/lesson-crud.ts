import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';
import type { LearnDocument } from '$lib/learn/document/types';

/** Builder persists LearnDocument v2 only (`learn_document` / `document` source). */
export type BuilderDocument = LearnDocument;

export type BuilderLessonSourceType =
	| 'manual'
	| 'v3_generation'
	| 'template'
	| 'document'
	| 'learn_document'
	| 'native_learn';

export interface BuilderLessonSummary {
	id: string;
	source_generation_id: string | null;
	source_type: BuilderLessonSourceType;
	title: string;
	class_label: string | null;
	created_at: string;
	updated_at: string;
}

export interface BuilderLessonRecord extends BuilderLessonSummary {
	document: BuilderDocument;
}

export interface CreateBuilderLessonRequest {
	title?: string;
	class_label?: string | null;
	source_generation_id?: string;
	source_type?: BuilderLessonSourceType;
	document: BuilderDocument;
}

export interface UpdateBuilderLessonRequest {
	title?: string;
	class_label?: string | null;
	document: BuilderDocument;
}

export async function createBuilderLesson(
	request: CreateBuilderLessonRequest
): Promise<BuilderLessonRecord> {
	const response = await apiFetch('/api/v1/builder/lessons', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request)
	});
	await ensureOk(response, 'Failed to create builder lesson.');
	return response.json() as Promise<BuilderLessonRecord>;
}

export async function listBuilderLessons(): Promise<BuilderLessonSummary[]> {
	const response = await apiFetch('/api/v1/builder/lessons');
	await ensureOk(response, 'Failed to load builder lessons.');
	return response.json() as Promise<BuilderLessonSummary[]>;
}

export async function getBuilderLesson(id: string): Promise<BuilderLessonRecord> {
	const response = await apiFetch(`/api/v1/builder/lessons/${encodeURIComponent(id)}`);
	await ensureOk(response, 'Failed to load builder lesson.');
	return response.json() as Promise<BuilderLessonRecord>;
}

export async function updateBuilderLesson(
	id: string,
	request: UpdateBuilderLessonRequest
): Promise<BuilderLessonRecord> {
	const response = await apiFetch(`/api/v1/builder/lessons/${encodeURIComponent(id)}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request)
	});
	await ensureOk(response, 'Failed to save builder lesson.');
	return response.json() as Promise<BuilderLessonRecord>;
}

export async function deleteBuilderLesson(id: string): Promise<void> {
	const response = await apiFetch(`/api/v1/builder/lessons/${encodeURIComponent(id)}`, {
		method: 'DELETE'
	});
	await ensureOk(response, 'Failed to delete builder lesson.');
}
