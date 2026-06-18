import type {
	BriefRequest,
	BriefResponse,
	GenerationAccepted,
	GenerationDetail,
	GenerationDocument,
	GenerationHistoryItem,
	GenerationRequest,
	PDFExportRequest
} from '$lib/types';
import { fetchEventSource } from '@microsoft/fetch-event-source';
import { ensureOk } from '$lib/api/errors';
import { get } from 'svelte/store';
import { authToken } from '$lib/stores/auth';
import { resolveClientApiBase, type ApiEnvironment } from './config';


const API_BASE = resolveClientApiBase(import.meta.env as ApiEnvironment);

export function buildApiUrl(path: string): string {
	return API_BASE ? `${API_BASE}${path}` : path;
}

export function apiFetch(path: string, init?: RequestInit): Promise<Response> {
	const token = getAuthToken();
	const headers = new Headers(init?.headers);
	if (token) {
		headers.set('Authorization', `Bearer ${token}`);
	}
	return fetch(buildApiUrl(path), { ...init, headers });
}

export async function startGeneration(request: GenerationRequest): Promise<GenerationAccepted> {
	const response = await apiFetch('/api/v1/generations', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request)
	});
	await ensureOk(response, 'Generation failed.');
	return response.json();
}

export async function planBrief(request: BriefRequest): Promise<BriefResponse> {
	const response = await apiFetch('/api/v1/brief', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request)
	});
	await ensureOk(response, 'Brief planning failed.');
	return response.json();
}

export async function getGenerations(limit = 20, offset = 0): Promise<GenerationHistoryItem[]> {
	const response = await apiFetch(`/api/v1/generations?limit=${limit}&offset=${offset}`);
	await ensureOk(response, 'Failed to fetch generations.');
	return response.json();
}

export async function getGenerationDetail(id: string): Promise<GenerationDetail> {
	const response = await apiFetch(`/api/v1/generations/${id}`);
	await ensureOk(response, 'Failed to fetch generation detail.');
	return response.json();
}

export async function getGenerationDocument(id: string): Promise<GenerationDocument> {
	const response = await apiFetch(`/api/v1/generations/${id}/document`);
	await ensureOk(response, 'Failed to fetch document.');
	return response.json();
}

export function buildGenerationEventsUrl(id: string): string {
	return buildApiUrl(`/api/v1/generations/${encodeURIComponent(id)}/events`);
}

export function connectGenerationEvents(
	id: string,
	handlers: {
		onEvent: (eventType: string, data: string) => void;
		onError: (err: unknown) => void;
		onOpen?: () => void;
	}
): () => void {
	const ctrl = new AbortController();
	const url = buildApiUrl(`/api/v1/generations/${encodeURIComponent(id)}/events`);
	const token = getAuthToken();
	const headers: Record<string, string> = {};
	if (token) {
		headers['Authorization'] = `Bearer ${token}`;
	}

	fetchEventSource(url, {
		signal: ctrl.signal,
		headers,
		async onopen(response) {
			if (!response.ok) {
				throw new Error(`SSE connection failed: ${response.status}`);
			}
			handlers.onOpen?.();
		},
		onmessage(msg) {
			handlers.onEvent(msg.event ?? '', msg.data ?? '');
		},
		onerror(err) {
			handlers.onError(err);
			throw err; // stop fetchEventSource auto-retry; components own reconnect logic
		},
	});

	return () => ctrl.abort();
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
	const response = await fetch(buildApiUrl('/health'));
	return response.json();
}

export async function downloadGenerationPdf(
	id: string,
	request: PDFExportRequest
): Promise<{ filename: string | null; pageCount: string | null }> {
	const response = await apiFetch(`/api/v1/generations/${encodeURIComponent(id)}/export/pdf`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request)
	});
	await ensureOk(response, 'Failed to export PDF.');

	const blob = await response.blob();
	const downloadUrl = URL.createObjectURL(blob);
	const anchor = document.createElement('a');
	const filename = parseFilename(response.headers.get('content-disposition'));
	anchor.href = downloadUrl;
	anchor.download = filename ?? 'textbook.pdf';
	anchor.click();
	URL.revokeObjectURL(downloadUrl);

	return {
		filename,
		pageCount: response.headers.get('x-page-count')
	};
}

function getAuthToken(): string | null {
	return get(authToken) ?? getQueryToken();
}

function getQueryToken(): string | null {
	if (typeof window === 'undefined') {
		return null;
	}
	return new URL(window.location.href).searchParams.get('token');
}

function parseFilename(header: string | null): string | null {
	if (!header) {
		return null;
	}
	const match = /filename="?([^";]+)"?/i.exec(header);
	return match?.[1] ?? null;
}
