import { ensureOk } from '$lib/api/errors';
import type {
	GenerationAccepted,
	PlanningStreamEvent,
	PlanningGenerationSpec,
	StudioBriefRequest,
	StudioTemplateContract
} from '$lib/types';

import { apiFetch } from './client';

function parseSseEventChunk(chunk: string): PlanningStreamEvent | null {
	let eventName = '';
	const dataLines: string[] = [];

	for (const rawLine of chunk.split(/\r?\n/)) {
		const line = rawLine.trim();
		if (!line || line.startsWith(':')) continue;
		if (line.startsWith('event:')) {
			eventName = line.slice('event:'.length).trim();
			continue;
		}
		if (line.startsWith('data:')) {
			dataLines.push(line.slice('data:'.length).trim());
		}
	}

	if (!eventName || dataLines.length === 0) {
		return null;
	}

	return {
		event: eventName,
		data: JSON.parse(dataLines.join('\n'))
	} as PlanningStreamEvent;
}

function extractNextChunk(buffer: string): { chunk: string; rest: string } | null {
	const match = /\r?\n\r?\n/.exec(buffer);
	if (!match || match.index < 0) {
		return null;
	}

	return {
		chunk: buffer.slice(0, match.index),
		rest: buffer.slice(match.index + match[0].length)
	};
}

export async function* streamPlan(
	request: StudioBriefRequest
): AsyncGenerator<PlanningStreamEvent> {
	const response = await apiFetch('/api/v1/brief/stream', {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'text/event-stream'
		},
		body: JSON.stringify(request)
	});
	await ensureOk(response, 'Brief planning failed.');

	if (!response.body) {
		throw new Error('Planning response did not include a stream.');
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = '';

	while (true) {
		const { value, done } = await reader.read();
		if (done) {
			buffer += decoder.decode();
			break;
		}
		buffer += decoder.decode(value, { stream: true });

		while (true) {
			const next = extractNextChunk(buffer);
			if (!next) {
				break;
			}
			buffer = next.rest;
			const event = parseSseEventChunk(next.chunk);
			if (event) {
				yield event;
			}
		}
	}

	if (buffer.trim()) {
		const event = parseSseEventChunk(buffer.trim());
		if (event) {
			yield event;
		}
	}
}

export async function* streamReplan(
	brief: StudioBriefRequest,
	forced_template_id: string
): AsyncGenerator<PlanningStreamEvent> {
	yield* streamPlan({ ...brief, forced_template_id });
}

export async function commitPlan(spec: PlanningGenerationSpec): Promise<GenerationAccepted> {
	const response = await apiFetch('/api/v1/brief/commit', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(spec)
	});
	await ensureOk(response, 'Failed to commit lesson plan.');
	return response.json();
}

export async function listContracts(): Promise<StudioTemplateContract[]> {
	const response = await apiFetch('/api/v1/contracts');
	await ensureOk(response, 'Failed to fetch template contracts.');
	return response.json();
}
