import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';

export interface UploadedLessonMedia {
	id: string;
	type: 'image';
	url: string;
	mime_type: string;
	filename?: string | null;
	source?: 'upload';
}

export async function uploadLessonMedia(lessonId: string, file: File): Promise<UploadedLessonMedia> {
	const form = new FormData();
	form.append('file', file);

	const response = await apiFetch(
		`/api/v1/builder/lessons/${encodeURIComponent(lessonId)}/media/upload`,
		{
			method: 'POST',
			body: form
		}
	);
	await ensureOk(response, 'Failed to upload image.');
	return response.json() as Promise<UploadedLessonMedia>;
}
