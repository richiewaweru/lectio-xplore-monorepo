import { fetchEventSource } from '@microsoft/fetch-event-source';
import { get } from 'svelte/store';

import { ensureOk } from '$lib/api/errors';
import { apiFetch, buildApiUrl } from '$lib/api/client';
import { authToken } from '$lib/stores/auth';
import type {
	BlueprintPreviewDTO,
	V3ChunkedPlan,
	V3ChunkedPlanState,
	V3ChunkedStatus,
	V3GenerationDetail,
	V3GenerationHistoryItem,
	V3InputForm,
	V3IntentDrafts,
	V3DraftPack,
	V3SignalSummary,
	V3VariantSpec,
	V3XplorePack
} from '$lib/types/v3';

export interface V3SubtopicCandidate {
	id: string;
	title: string;
	description: string;
}

function bearerHeaders(): Record<string, string> {
	const headers: Record<string, string> = { 'Content-Type': 'application/json' };
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;
	return headers;
}

export async function extractSignals(form: V3InputForm): Promise<V3SignalSummary> {
	const res = await apiFetch('/api/v1/v3/signals', {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify(form)
	});
	await ensureOk(res, 'Could not read your teaching brief.');
	return res.json() as Promise<V3SignalSummary>;
}

export async function narrowTopic(payload: {
	topic: string;
	grade_level: string;
	subject: string;
}): Promise<V3SubtopicCandidate[]> {
	const res = await apiFetch('/api/v1/v3/narrow', {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify(payload)
	});
	await ensureOk(res, 'Could not narrow this topic.');
	const data = (await res.json()) as { candidates: V3SubtopicCandidate[] };
	return data.candidates ?? [];
}

export async function proposeIntent(payload: {
	grade_level: string;
	subject: string;
	resource_type: string;
	duration_minutes: number;
	learner_level: string;
	reading_level: string;
	language_support: string;
	prior_knowledge_level: string;
	topic: string;
	subtopics: string[];
}): Promise<V3IntentDrafts> {
	const res = await apiFetch('/api/v1/v3/propose-intent', {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify(payload)
	});
	await ensureOk(res, 'Could not draft the lesson intent.');
	return res.json() as Promise<V3IntentDrafts>;
}

export async function startChunkedPlan(payload: {
	signals: V3SignalSummary;
	form: V3InputForm;
	variants?: V3VariantSpec[];
}): Promise<V3ChunkedPlanState> {
	const res = await apiFetch('/api/v1/v3/chunked/plan/start', {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify(payload)
	});
	await ensureOk(res, 'Could not build the structural lesson plan.');
	return res.json() as Promise<V3ChunkedPlanState>;
}

export async function getXplorePack(packId: string): Promise<V3XplorePack> {
	const res = await apiFetch(`/api/v1/v3/packs/${encodeURIComponent(packId)}`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load this Xplore pack.');
	return res.json() as Promise<V3XplorePack>;
}

export async function retryXploreVariant(
	packId: string,
	variantLabel: string
): Promise<V3XplorePack> {
	const res = await apiFetch(
		`/api/v1/v3/packs/${encodeURIComponent(packId)}/variants/${encodeURIComponent(variantLabel)}/retry`,
		{ method: 'POST', headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not retry this booklet.');
	return res.json() as Promise<V3XplorePack>;
}

export async function deleteXploreVariant(
	packId: string,
	variantLabel: string
): Promise<V3XplorePack> {
	const res = await apiFetch(
		`/api/v1/v3/packs/${encodeURIComponent(packId)}/variants/${encodeURIComponent(variantLabel)}`,
		{ method: 'DELETE', headers: bearerHeaders() }
	);
	await ensureOk(res, 'Could not remove this booklet.');
	return res.json() as Promise<V3XplorePack>;
}

export async function approveChunkedPlan(
	generationId: string,
	payload: { display_title?: string } = {}
): Promise<V3ChunkedPlanState> {
	const res = await apiFetch(`/api/v1/v3/chunked/${encodeURIComponent(generationId)}/approve`, {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify({ display_title: payload.display_title ?? null })
	});
	await ensureOk(res, 'Could not start section expansion.');
	return res.json() as Promise<V3ChunkedPlanState>;
}

export async function regenerateChunkedPlan(payload: {
	generation_id: string;
	note?: string;
}): Promise<V3ChunkedPlanState> {
	const res = await apiFetch(
		`/api/v1/v3/chunked/${encodeURIComponent(payload.generation_id)}/regenerate`,
		{
			method: 'POST',
			headers: bearerHeaders(),
			body: JSON.stringify({ note: payload.note ?? '' })
		}
	);
	await ensureOk(res, 'Could not regenerate the structural plan.');
	return res.json() as Promise<V3ChunkedPlanState>;
}

export async function retryChunkedSection(payload: {
	generation_id: string;
	section_id: string;
}): Promise<V3ChunkedPlanState> {
	const res = await apiFetch(
		`/api/v1/v3/chunked/${encodeURIComponent(payload.generation_id)}/retry-section`,
		{
			method: 'POST',
			headers: bearerHeaders(),
			body: JSON.stringify({ section_id: payload.section_id })
		}
	);
	await ensureOk(res, 'Could not retry this section.');
	return res.json() as Promise<V3ChunkedPlanState>;
}

export async function getChunkedPlan(generationId: string): Promise<V3ChunkedPlan> {
	const res = await apiFetch(`/api/v1/v3/chunked/${encodeURIComponent(generationId)}/plan`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load the structural lesson plan.');
	return res.json() as Promise<V3ChunkedPlan>;
}

export async function getChunkedPlanStatus(generationId: string): Promise<V3ChunkedStatus> {
	const res = await apiFetch(`/api/v1/v3/chunked/${encodeURIComponent(generationId)}/status`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load chunked planning status.');
	return res.json() as Promise<V3ChunkedStatus>;
}

export type V3VisualBlock = NonNullable<V3DraftPack['visual_blocks']>[number];

export async function regenerateV3Visual(payload: {
	generation_id: string;
	visual_id: string;
	teacher_hint?: string;
}): Promise<V3VisualBlock> {
	const res = await apiFetch(
		`/api/v1/v3/generations/${encodeURIComponent(payload.generation_id)}/visuals/${encodeURIComponent(payload.visual_id)}/regenerate`,
		{
			method: 'POST',
			headers: bearerHeaders(),
			body: JSON.stringify({ teacher_hint: payload.teacher_hint ?? '' })
		}
	);
	await ensureOk(res, 'Could not regenerate this image.');
	return res.json() as Promise<V3VisualBlock>;
}

export async function adjustBlueprint(payload: {
	blueprint_id: string;
	adjustment: string;
}): Promise<BlueprintPreviewDTO> {
	const res = await apiFetch('/api/v1/v3/blueprint/adjust', {
		method: 'POST',
		headers: bearerHeaders(),
		body: JSON.stringify(payload)
	});
	await ensureOk(res, 'Could not update the lesson plan.');
	return res.json() as Promise<BlueprintPreviewDTO>;
}

export type V3StudioStreamHandlers = {
	onPoke?: () => void;
	onOpen?: () => void;
	onError?: (err: unknown) => void;
};

export interface V3ChunkedStreamHandlers {
	onSectionStart?: (sectionId: string) => void;
	onSectionDone?: (
		sectionId: string,
		brief?: {
			components: { component_id: string; content_intent: string }[];
			question_prompts: string[];
			visual_subject: string | null;
		}
	) => void;
	onSectionRetry?: (sectionId: string, attempt: number) => void;
	onSectionFailed?: (sectionId: string, errors: string[]) => void;
	onStage2Complete?: (failedSections: string[]) => void;
	onAssemblyBlocked?: (failedSections: string[]) => void;
	onError?: (msg: string) => void;
}

export type V3DocumentResponse = Record<string, unknown>;

export async function fetchV3Document(generationId: string): Promise<V3DocumentResponse> {
	const res = await apiFetch(`/api/v1/v3/generations/${encodeURIComponent(generationId)}/document`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load generated document.');
	return res.json() as Promise<V3DocumentResponse>;
}

export async function getV3Generations(limit = 20, offset = 0): Promise<V3GenerationHistoryItem[]> {
	const res = await apiFetch(`/api/v1/v3/generations?limit=${limit}&offset=${offset}`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load V3 generation history.');
	return res.json() as Promise<V3GenerationHistoryItem[]>;
}

export async function getV3GenerationDetail(generationId: string): Promise<V3GenerationDetail> {
	const res = await apiFetch(`/api/v1/v3/generations/${encodeURIComponent(generationId)}`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load V3 generation detail.');
	return res.json() as Promise<V3GenerationDetail>;
}

export async function getV3GenerationBlueprint(generationId: string): Promise<BlueprintPreviewDTO> {
	const res = await apiFetch(`/api/v1/v3/generations/${encodeURIComponent(generationId)}/blueprint`, {
		method: 'GET',
		headers: bearerHeaders()
	});
	await ensureOk(res, 'Could not load generation blueprint.');
	return res.json() as Promise<BlueprintPreviewDTO>;
}

export function connectV3StudioGenerationStream(
	generationId: string,
	handlers: V3StudioStreamHandlers
): () => void {
	const ctrl = new AbortController();
	let lastPokeAt = 0;
	let pokeTimer: ReturnType<typeof setTimeout> | null = null;
	const url = buildApiUrl(`/api/v1/v3/generations/${encodeURIComponent(generationId)}/events`);
	const headers: Record<string, string> = {};
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;

	function pokeSoon(): void {
		const now = Date.now();
		const elapsed = now - lastPokeAt;
		if (elapsed >= 1000) {
			lastPokeAt = now;
			handlers.onPoke?.();
			return;
		}
		if (pokeTimer) return;
		pokeTimer = setTimeout(() => {
			pokeTimer = null;
			lastPokeAt = Date.now();
			handlers.onPoke?.();
		}, 1000 - elapsed);
	}

	fetchEventSource(url, {
		signal: ctrl.signal,
		headers,
		async onopen(response) {
			if (!response.ok) {
				throw new Error(`v3 SSE failed: ${response.status}`);
			}
			handlers.onOpen?.();
		},
		onmessage() {
			pokeSoon();
		},
		onerror(err) {
			handlers.onError?.(err);
			console.warn('[v3 generation stream] closed; document polling remains active', err);
			ctrl.abort();
			throw err;
		}
	});

	return () => {
		if (pokeTimer) {
			clearTimeout(pokeTimer);
			pokeTimer = null;
		}
		ctrl.abort();
	};
}

export function connectV3ChunkedStream(
	generationId: string,
	handlers: V3ChunkedStreamHandlers
): () => void {
	const ctrl = new AbortController();
	const url = buildApiUrl(`/api/v1/v3/chunked/${encodeURIComponent(generationId)}/events`);
	const headers: Record<string, string> = {};
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;

	fetchEventSource(url, {
		signal: ctrl.signal,
		headers,
		async onopen(response) {
			if (!response.ok) {
				throw new Error(`chunked SSE failed: ${response.status}`);
			}
		},
		onmessage(msg) {
			const type = msg.event ?? '';
			let payload: Record<string, unknown> = {};
			try {
				payload = JSON.parse(msg.data ?? '{}') as Record<string, unknown>;
			} catch {
				payload = {};
			}
			switch (type) {
				case 'stage2_section_start':
					handlers.onSectionStart?.(String(payload.section_id ?? ''));
					break;
				case 'stage2_section_done':
					handlers.onSectionDone?.(
						String(payload.section_id ?? ''),
						payload.brief as
							| {
									components: { component_id: string; content_intent: string }[];
									question_prompts: string[];
									visual_subject: string | null;
							  }
							| undefined
					);
					break;
				case 'stage2_section_retry':
					handlers.onSectionRetry?.(
						String(payload.section_id ?? ''),
						Number(payload.attempt ?? 2)
					);
					break;
				case 'stage2_section_failed':
					handlers.onSectionFailed?.(
						String(payload.section_id ?? ''),
						Array.isArray(payload.errors)
							? payload.errors.filter((item): item is string => typeof item === 'string')
							: []
					);
					break;
				case 'stage2_complete':
					handlers.onStage2Complete?.(
						Array.isArray(payload.failed_sections)
							? payload.failed_sections.filter((item): item is string => typeof item === 'string')
							: []
					);
					break;
				case 'assembly_blocked':
					handlers.onAssemblyBlocked?.(
						Array.isArray(payload.failed_sections)
							? payload.failed_sections.filter((item): item is string => typeof item === 'string')
							: []
					);
					break;
				case 'generation_warning':
					handlers.onError?.(String(payload.message ?? 'Unknown error'));
					break;
				default:
					break;
			}
		},
		onerror(err) {
			handlers.onError?.(String(err));
		}
	});

	return () => ctrl.abort();
}

export type V3PdfExportBody = {
	school_name: string;
	teacher_name: string;
	date?: string | null;
	include_toc: boolean;
	include_answers: boolean;
};

export async function downloadV3GenerationPdf(
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
	a.download = `lesson-${generationId}.pdf`;
	a.click();
	URL.revokeObjectURL(url);
}
