import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';
import type { LessonDocument } from '@lectio/learn';

export interface LearnReleaseSummary {
	id: string;
	editable_lesson_id: string;
	release_number: number;
	title: string;
	document_hash: string;
	status: string;
	published_at: string;
}

export interface LearnReleaseRecord extends LearnReleaseSummary {
	document: LessonDocument;
	source_generation_id?: string | null;
	path_lesson_id?: string | null;
}

export async function publishLearnRelease(
	lessonId: string,
	body: { title?: string; path_lesson_id?: string } = {}
): Promise<LearnReleaseRecord> {
	const response = await apiFetch(`/api/v1/learn/lessons/${lessonId}/releases`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	await ensureOk(response);
	return (await response.json()) as LearnReleaseRecord;
}

export async function listLearnReleases(lessonId: string): Promise<LearnReleaseSummary[]> {
	const response = await apiFetch(`/api/v1/learn/lessons/${lessonId}/releases`);
	await ensureOk(response);
	return (await response.json()) as LearnReleaseSummary[];
}

export async function getLearnRelease(releaseId: string): Promise<LearnReleaseRecord> {
	const response = await apiFetch(`/api/v1/learn/releases/${releaseId}`);
	await ensureOk(response);
	return (await response.json()) as LearnReleaseRecord;
}
