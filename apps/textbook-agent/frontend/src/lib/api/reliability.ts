/**
 * Shared reliability transport (status + replayable events).
 * Domain stores may use this; they must not import sibling domain internals.
 *
 * Backend (P04): `/api/v1/realizations/{realization_id}/status|events|events/stream`
 */

import { fetchEventSource } from '@microsoft/fetch-event-source';
import { get } from 'svelte/store';

import { apiFetch, buildApiUrl } from '$lib/api/client';
import { ensureOk } from '$lib/api/errors';
import { authToken } from '$lib/shared/stores/auth';
import type {
	ReliabilityProgressEvent,
	ReliabilityRunStatus
} from '$lib/types/reliability';

export function reliabilityStatusPath(runId: string): string {
	return `/api/v1/realizations/${encodeURIComponent(runId)}/status`;
}

export function reliabilityEventsPath(runId: string, afterSequence = 0): string {
	const base = `/api/v1/realizations/${encodeURIComponent(runId)}/events`;
	return afterSequence > 0 ? `${base}?after_seq=${afterSequence}` : base;
}

export function reliabilityEventsStreamPath(runId: string, afterSequence = 0): string {
	const base = `/api/v1/realizations/${encodeURIComponent(runId)}/events/stream`;
	return afterSequence > 0 ? `${base}?after_seq=${afterSequence}` : base;
}

type BackendStatus = {
	run_id: string;
	path: string;
	status: string;
	stage: string;
	active_items?: Array<{ item_id: string; stage: string; attempt: number; state?: string }>;
	completed?: number;
	total?: number;
	retry_schedule?: Array<{ item_id: string; attempt: number; next_retry_at: string }>;
	allowed_actions?: string[];
	revisions?: {
		realization_revision?: number;
		teaching_plan_revision?: number;
		document_revision?: number;
	};
	latest_seq?: number;
	owner_user_id?: string;
};

export function mapBackendStatus(raw: BackendStatus): ReliabilityRunStatus {
	const nextRetry = raw.retry_schedule?.[0]?.next_retry_at ?? null;
	return {
		run_id: raw.run_id,
		owner_id: raw.owner_user_id ?? '',
		path: raw.path,
		stage: raw.stage,
		status: raw.status,
		active_items: raw.active_items ?? [],
		completed_count: raw.completed ?? null,
		total_count: raw.total ?? null,
		next_retry_at: nextRetry,
		allowed_actions: (raw.allowed_actions ?? []) as ReliabilityRunStatus['allowed_actions'],
		document_revision: raw.revisions?.document_revision ?? null,
		path_revision: raw.revisions?.teaching_plan_revision ?? null,
		last_sequence: raw.latest_seq ?? 0
	};
}

export async function getReliabilityRunStatus(runId: string): Promise<ReliabilityRunStatus> {
	const response = await apiFetch(reliabilityStatusPath(runId));
	await ensureOk(response, 'Could not load run status.');
	const raw = (await response.json()) as BackendStatus;
	return mapBackendStatus(raw);
}

export interface ReliabilityEventHandlers {
	onEvent?: (event: ReliabilityProgressEvent) => void;
	onOpen?: () => void;
	onError?: (error: unknown) => void;
}

export interface ReliabilitySubscriptionOptions {
	ownerId: string;
	runId: string;
	afterSequence?: number;
	handlers: ReliabilityEventHandlers;
	/** Injected for tests; defaults to fetchEventSource. */
	connect?: typeof fetchEventSource;
}

type BackendEvent = {
	seq?: number;
	sequence?: number;
	event_type?: string;
	at?: string;
	occurred_at?: string;
	run_id: string;
	path?: string;
	stage?: string;
	item_id?: string | null;
	attempt?: number | null;
	error_category?: string | null;
	payload?: Record<string, unknown>;
	owner_id?: string;
	owner_user_id?: string;
};

export function mapBackendEvent(raw: BackendEvent, fallbackOwnerId: string): ReliabilityProgressEvent | null {
	const sequence = raw.sequence ?? raw.seq;
	if (typeof sequence !== 'number') return null;
	return {
		sequence,
		run_id: raw.run_id,
		owner_id: raw.owner_id ?? raw.owner_user_id ?? fallbackOwnerId,
		path: raw.path ?? '',
		stage: raw.stage ?? '',
		item_id: raw.item_id ?? null,
		attempt: raw.attempt ?? null,
		event_type: raw.event_type ?? 'progress',
		occurred_at: raw.occurred_at ?? raw.at ?? '',
		error_category: raw.error_category ?? null,
		message: typeof raw.payload?.message === 'string' ? raw.payload.message : null
	};
}

/**
 * Subscribe to a single owner/run event stream. Caller must invoke the
 * returned dispose function on navigate/unmount. Events for other runs or
 * out-of-order/stale sequences are ignored by {@link createScopedEventSink}.
 */
export function subscribeReliabilityEvents(options: ReliabilitySubscriptionOptions): () => void {
	const ctrl = new AbortController();
	const after = options.afterSequence ?? 0;
	const url = buildApiUrl(reliabilityEventsStreamPath(options.runId, after));
	const headers: Record<string, string> = {};
	const token = get(authToken);
	if (token) headers.Authorization = `Bearer ${token}`;

	const connect = options.connect ?? fetchEventSource;
	connect(url, {
		signal: ctrl.signal,
		headers,
		async onopen(response) {
			if (!response.ok) {
				throw new Error(`reliability SSE failed: ${response.status}`);
			}
			options.handlers.onOpen?.();
		},
		onmessage(msg) {
			let payload: ReliabilityProgressEvent | null = null;
			try {
				const raw = JSON.parse(msg.data ?? '{}') as BackendEvent;
				payload = mapBackendEvent(raw, options.ownerId);
			} catch {
				payload = null;
			}
			if (!payload) return;
			options.handlers.onEvent?.(payload);
		},
		onerror(err) {
			options.handlers.onError?.(err);
			ctrl.abort();
			throw err;
		}
	});

	return () => ctrl.abort();
}

export interface ScopedEventSink {
	readonly ownerId: string;
	readonly runId: string;
	readonly lastSequence: number;
	readonly disposed: boolean;
	accept(event: ReliabilityProgressEvent): ReliabilityProgressEvent | null;
	dispose(): void;
}

/** Ignore events after dispose, wrong owner/run, or non-increasing sequence. */
export function createScopedEventSink(ownerId: string, runId: string, startSequence = 0): ScopedEventSink {
	let lastSequence = startSequence;
	let disposed = false;

	return {
		get ownerId() {
			return ownerId;
		},
		get runId() {
			return runId;
		},
		get lastSequence() {
			return lastSequence;
		},
		get disposed() {
			return disposed;
		},
		accept(event: ReliabilityProgressEvent) {
			if (disposed) return null;
			if (event.owner_id !== ownerId || event.run_id !== runId) return null;
			if (event.sequence <= lastSequence) return null;
			lastSequence = event.sequence;
			return event;
		},
		dispose() {
			disposed = true;
		}
	};
}

export interface ManagedReliabilitySubscription {
	readonly sink: ScopedEventSink;
	dispose(): void;
	reconnect(afterSequence?: number): void;
}

/**
 * Owns one subscription scoped to owner+run. Reconnect aborts the prior
 * stream before opening a new one (no duplicate listeners).
 */
export function createManagedReliabilitySubscription(
	ownerId: string,
	runId: string,
	handlers: ReliabilityEventHandlers,
	options: {
		afterSequence?: number;
		subscribe?: typeof subscribeReliabilityEvents;
	} = {}
): ManagedReliabilitySubscription {
	const sink = createScopedEventSink(ownerId, runId, options.afterSequence ?? 0);
	const subscribe = options.subscribe ?? subscribeReliabilityEvents;
	let unsubscribe: (() => void) | null = null;

	function wire(afterSequence: number): void {
		unsubscribe?.();
		unsubscribe = subscribe({
			ownerId,
			runId,
			afterSequence,
			handlers: {
				onOpen: handlers.onOpen,
				onError: handlers.onError,
				onEvent(event) {
					const accepted = sink.accept(event);
					if (accepted) handlers.onEvent?.(accepted);
				}
			}
		});
	}

	wire(options.afterSequence ?? 0);

	return {
		sink,
		dispose() {
			sink.dispose();
			unsubscribe?.();
			unsubscribe = null;
		},
		reconnect(afterSequence?: number) {
			if (sink.disposed) return;
			wire(afterSequence ?? sink.lastSequence);
		}
	};
}
