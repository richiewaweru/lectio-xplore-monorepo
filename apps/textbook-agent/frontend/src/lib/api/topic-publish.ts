import { apiFetch } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';

export interface TeacherClass {
	id: string;
	name: string;
}

export type PublishCandidateStatus = 'not_generated' | 'ready_to_publish' | 'published';

export interface PublishCandidate {
	path_lesson_id: string;
	position: number;
	title: string;
	generated: boolean;
	editable_lesson_id: string | null;
	release_id: string | null;
	release_number: number | null;
	has_unpublished_changes: boolean;
	assigned_to_class: boolean | null;
	status: PublishCandidateStatus;
}

export interface PublishCandidatesResponse {
	unit_id: string;
	unit_title: string;
	class_id: string | null;
	lessons: PublishCandidate[];
}

export type PublishItemStatus = 'not_generated' | 'published' | 'already_published' | 'failed';

export interface PublishItemResult {
	path_lesson_id: string;
	position: number;
	title: string;
	status: PublishItemStatus;
	release_id: string | null;
	release_number: number | null;
	release_created: boolean;
	assignment_id: string | null;
	assignment_created: boolean;
	message: string | null;
}

export interface PublishToClassResponse {
	unit_id: string;
	class_id: string;
	results: PublishItemResult[];
}

export const RELEASE_NOT_LINKED_MESSAGE =
	'This lesson is not linked to a topic lesson, so it cannot be added to a class topic path. Publish it again and choose which topic lesson it is.';

/** Raised when the class flow refuses a release that has no topic-path link. */
export class ReleaseNotLinkedError extends Error {
	constructor(message: string = RELEASE_NOT_LINKED_MESSAGE) {
		super(message);
		this.name = 'ReleaseNotLinkedError';
	}
}

export async function listTeacherClasses(): Promise<TeacherClass[]> {
	const response = await apiFetch('/api/v1/learn/classes');
	await ensureOk(response);
	return (await response.json()) as TeacherClass[];
}

export async function getPublishCandidates(
	unitId: string,
	classId?: string | null
): Promise<PublishCandidatesResponse> {
	const query = classId ? `?class_id=${encodeURIComponent(classId)}` : '';
	const response = await apiFetch(
		`/api/v1/units/${encodeURIComponent(unitId)}/publish-candidates${query}`
	);
	await ensureOk(response);
	return (await response.json()) as PublishCandidatesResponse;
}

export async function publishUnitToClass(
	unitId: string,
	body: { class_id: string; path_lesson_ids: string[] }
): Promise<PublishToClassResponse> {
	const response = await apiFetch(`/api/v1/units/${encodeURIComponent(unitId)}/publish-to-class`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	await ensureOk(response);
	return (await response.json()) as PublishToClassResponse;
}

/** Assign a release to a class through the topic-path flow (link required). */
export async function assignReleaseToClass(body: {
	learn_release_id: string;
	title: string;
	class_id: string;
	mode: string;
}): Promise<void> {
	const response = await apiFetch('/api/v1/learn/assignments', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			learn_release_id: body.learn_release_id,
			title: body.title,
			class_ids: [body.class_id],
			mode: body.mode,
			require_path_lesson_id: true
		})
	});
	if (response.status === 422) {
		let code: unknown = null;
		try {
			const payload = (await response.clone().json()) as { detail?: { code?: unknown } };
			code = payload?.detail?.code;
		} catch {
			code = null;
		}
		if (code === 'RELEASE_NOT_LINKED_TO_PATH_LESSON') throw new ReleaseNotLinkedError();
	}
	await ensureOk(response);
}
