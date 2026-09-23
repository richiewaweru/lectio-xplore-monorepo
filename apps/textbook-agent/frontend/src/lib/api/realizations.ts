import { get } from 'svelte/store';

import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';
import { authToken } from '$lib/shared/stores/auth';

export type V3VisualRetryResult = {
	retried?: number;
	succeeded?: number;
	failed?: number;
	[key: string]: unknown;
};

export type V3PdfExportBody = {
	school_name: string;
	teacher_name: string;
	date?: string | null;
	include_toc: boolean;
	include_answers: boolean;
	edition?: 'teacher' | 'student';
};

function bearerHeaders(): Record<string, string> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

export async function realizeLearnFromGeneration(generationId: string): Promise<{
	status: string;
	path: string;
	output_id: string;
	editable_lesson_id?: string | null;
	open_href?: string | null;
	workspace_href?: string | null;
	realization_id?: string;
	realization_revision?: number;
}> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/realize-learn`,
		{ method: 'POST', headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not generate the Learn lesson.');
	return res.json();
}

export async function realizePrintFromGeneration(generationId: string): Promise<{
	status: string;
	path: string;
	output_id: string;
	open_href?: string | null;
}> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/realize-print`,
		{ method: 'POST', headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not generate the Print lesson.');
	return res.json();
}

export async function retryNativeGeneration(generationId: string): Promise<void> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/retry-native`,
		{ method: 'POST', headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not retry the failed generation stage.');
}

export async function retryNativeVisuals(generationId: string): Promise<V3VisualRetryResult | null> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/visuals/retry`,
		{ method: 'POST', headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not retry failed visuals.');
	if (res.status === 204) return null;
	return (await res.json()) as V3VisualRetryResult;
}

export async function downloadGenerationPdf(
	generationId: string,
	body: V3PdfExportBody
): Promise<void> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(generationId)}/export/pdf`,
		{
			method: 'POST',
			headers: bearerHeaders(),
			body: JSON.stringify(body)
		}
	);
	await ensureOk(res, 'Failed to export PDF.');
	const blob = await res.blob();
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	const edition = body.edition ?? (body.include_answers ? 'teacher' : 'student');
	a.download = `lesson-${generationId}-${edition}.pdf`;
	document.body.appendChild(a);
	a.click();
	window.setTimeout(() => {
		a.remove();
		URL.revokeObjectURL(url);
	}, 60_000);
}
