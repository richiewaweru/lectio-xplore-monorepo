import type {
	ErrorEvent,
	GenerationDocument,
	MediaFrameFailedEvent,
	MediaFrameReadyEvent,
	MediaFrameStartedEvent,
	MediaPlanReadyEvent,
	MediaSlotFailedEvent,
	MediaSlotReadyEvent,
	ProgressUpdateEvent,
	QCCompleteEvent,
	RuntimePolicyEvent,
	RuntimeProgressEvent,
	SectionAssetPendingEvent,
	SectionAssetReadyEvent,
	SectionFailedEvent,
	SectionFinalEvent,
	SectionMediaBlockedEvent,
	SectionPartialEvent,
	SectionReadyEvent,
	SectionStartedEvent
} from '$lib/types';

import {
	applySectionAssetPending,
	applySectionAssetReady,
	applySectionFailed,
	applySectionFinal,
	applySectionPartial,
	applySectionReady,
	applySectionStarted,
	type ViewerSectionSignal
} from './viewer-state';

export interface GenerationStreamContext {
	document: GenerationDocument | null;
	plannedSections: number | null;
	qcSummary: { passed: number; total: number } | null;
	progressUpdate: ProgressUpdateEvent | null;
	runtimePolicy: RuntimePolicyEvent | null;
	runtimeProgress: RuntimeProgressEvent['snapshot'] | null;
	viewerWarning: string | null;
	activeSectionId: string | null;
	sectionSignals: Record<string, ViewerSectionSignal>;
}

export interface GenerationStreamOutcome {
	next: GenerationStreamContext;
	terminal:
		| {
				kind: 'complete' | 'generation_failed' | 'error';
				message?: string | null;
		  }
		| null;
}

function setSectionSignal(
	signals: Record<string, ViewerSectionSignal>,
	sectionId: string,
	signal: ViewerSectionSignal
): Record<string, ViewerSectionSignal> {
	const existing = signals[sectionId];
	if (
		existing &&
		existing.status === signal.status &&
		(existing.reason ?? null) === (signal.reason ?? null) &&
		JSON.stringify(existing.slot_ids ?? []) === JSON.stringify(signal.slot_ids ?? []) &&
		(existing.label ?? null) === (signal.label ?? null)
	) {
		return signals;
	}
	return { ...signals, [sectionId]: signal };
}

function isTerminalSectionSignal(signal: ViewerSectionSignal | undefined): boolean {
	return signal?.status === 'ready' || signal?.status === 'failed';
}

function normalizeRuntimeProgressSnapshot(
	snapshot: RuntimeProgressEvent['snapshot']
): RuntimeProgressEvent['snapshot'] {
	return snapshot;
}

function sameRuntimeProgressSnapshot(
	left: RuntimeProgressEvent['snapshot'] | null,
	right: RuntimeProgressEvent['snapshot']
): boolean {
	if (!left) return false;
	const normalizedLeft = normalizeRuntimeProgressSnapshot(left);
	const normalizedRight = normalizeRuntimeProgressSnapshot(right);
	return (
		normalizedLeft.mode === normalizedRight.mode &&
		normalizedLeft.sections_total === normalizedRight.sections_total &&
		normalizedLeft.sections_completed === normalizedRight.sections_completed &&
		normalizedLeft.sections_running === normalizedRight.sections_running &&
		normalizedLeft.sections_queued === normalizedRight.sections_queued &&
		normalizedLeft.media_running === normalizedRight.media_running &&
		normalizedLeft.media_queued === normalizedRight.media_queued &&
		normalizedLeft.qc_running === normalizedRight.qc_running &&
		normalizedLeft.qc_queued === normalizedRight.qc_queued &&
		normalizedLeft.retry_running === normalizedRight.retry_running &&
		normalizedLeft.retry_queued === normalizedRight.retry_queued
	);
}

function normalizeRuntimePolicyEvent(
	event: RuntimePolicyEvent
): RuntimePolicyEvent {
	return event;
}

function sameProgressUpdate(
	left: ProgressUpdateEvent | null,
	right: ProgressUpdateEvent
): boolean {
	if (!left) return false;
	return (
		left.stage === right.stage &&
		left.label === right.label &&
		(left.section_id ?? null) === (right.section_id ?? null)
	);
}

function isActiveSectionStage(stage: ProgressUpdateEvent['stage']): boolean {
	return stage === 'generating_section' || stage === 'repairing';
}

function applyMediaFrameSignal(
	context: GenerationStreamContext,
	payload: MediaFrameStartedEvent | MediaFrameReadyEvent | MediaFrameFailedEvent
): GenerationStreamContext {
	if (isTerminalSectionSignal(context.sectionSignals[payload.section_id])) {
		return context;
	}
	const current = context.sectionSignals[payload.section_id];
	const status: ViewerSectionSignal =
		payload.type === 'media_frame_started'
			? { status: 'generating' }
			: payload.type === 'media_frame_ready'
				? { status: 'partially_ready' }
				: current ?? { status: 'partially_ready' };

	return {
		...context,
		activeSectionId:
			payload.type === 'media_frame_started' ? payload.section_id : context.activeSectionId,
		sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, status)
	};
}

export function applyGenerationStreamEvent(
	context: GenerationStreamContext,
	type: string,
	data: string
): GenerationStreamOutcome {
	switch (type) {
		case 'pipeline_start': {
			const payload = JSON.parse(data) as { section_count: number };
			return {
				next: { ...context, plannedSections: payload.section_count },
				terminal: null
			};
		}
		case 'progress_update': {
			const payload = JSON.parse(data) as ProgressUpdateEvent;
			const shouldTrackActiveSection =
				Boolean(payload.section_id) &&
				isActiveSectionStage(payload.stage) &&
				!isTerminalSectionSignal(
					payload.section_id ? context.sectionSignals[payload.section_id] : undefined
				);
			const nextActiveSectionId =
				shouldTrackActiveSection && payload.section_id
					? payload.section_id
					: context.activeSectionId;
			if (
				sameProgressUpdate(context.progressUpdate, payload) &&
				nextActiveSectionId === context.activeSectionId
			) {
				return { next: context, terminal: null };
			}

			let nextSignals = context.sectionSignals;
			if (payload.section_id) {
				const existing = context.sectionSignals[payload.section_id];
				if (shouldTrackActiveSection) {
					nextSignals = setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'generating',
						label: payload.label
					});
				} else if (existing) {
					nextSignals = setSectionSignal(context.sectionSignals, payload.section_id, {
						...existing,
						label: payload.label
					});
				}
			}
			return {
				next: {
					...context,
					progressUpdate: payload,
					activeSectionId: nextActiveSectionId,
					sectionSignals: nextSignals
				},
				terminal: null
			};
		}
		case 'runtime_policy': {
			const payload = normalizeRuntimePolicyEvent(JSON.parse(data) as RuntimePolicyEvent);
			return {
				next: { ...context, runtimePolicy: payload },
				terminal: null
			};
		}
		case 'runtime_progress': {
			const payload = JSON.parse(data) as RuntimeProgressEvent;
			const normalizedSnapshot = normalizeRuntimeProgressSnapshot(payload.snapshot);
			const nextPlannedSections = context.plannedSections ?? payload.snapshot.sections_total;
			if (
				sameRuntimeProgressSnapshot(context.runtimeProgress, normalizedSnapshot) &&
				nextPlannedSections === context.plannedSections
			) {
				return { next: context, terminal: null };
			}
			return {
				next: {
					...context,
					runtimeProgress: normalizedSnapshot,
					plannedSections: nextPlannedSections
				},
				terminal: null
			};
		}
		case 'section_started': {
			if (!context.document) return { next: context, terminal: null };
			const payload = JSON.parse(data) as SectionStartedEvent;
			return {
				next: {
					...context,
					document: applySectionStarted(context.document, payload)
				},
				terminal: null
			};
		}
		case 'media_plan_ready': {
			const payload = JSON.parse(data) as MediaPlanReadyEvent;
			if (isTerminalSectionSignal(context.sectionSignals[payload.section_id])) {
				return { next: context, terminal: null };
			}
			return {
				next: {
					...context,
					sectionSignals: setSectionSignal(
						context.sectionSignals,
						payload.section_id,
						context.sectionSignals[payload.section_id] ?? { status: 'planned' }
					)
				},
				terminal: null
			};
		}
		case 'media_frame_started':
		case 'media_frame_ready':
		case 'media_frame_failed': {
			return {
				next: applyMediaFrameSignal(
					context,
					JSON.parse(data) as MediaFrameStartedEvent | MediaFrameReadyEvent | MediaFrameFailedEvent
				),
				terminal: null
			};
		}
		case 'media_slot_ready': {
			const payload = JSON.parse(data) as MediaSlotReadyEvent;
			if (isTerminalSectionSignal(context.sectionSignals[payload.section_id])) {
				return { next: context, terminal: null };
			}
			return {
				next: {
					...context,
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'partially_ready'
					})
				},
				terminal: null
			};
		}
		case 'media_slot_failed': {
			const payload = JSON.parse(data) as MediaSlotFailedEvent;
			if (isTerminalSectionSignal(context.sectionSignals[payload.section_id])) {
				return { next: context, terminal: null };
			}
			return {
				next: {
					...context,
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'partially_ready',
						reason: payload.error ?? null,
						slot_ids: [payload.slot_id]
					})
				},
				terminal: null
			};
		}
		case 'section_media_blocked': {
			const payload = JSON.parse(data) as SectionMediaBlockedEvent;
			if (isTerminalSectionSignal(context.sectionSignals[payload.section_id])) {
				return { next: context, terminal: null };
			}
			return {
				next: {
					...context,
					activeSectionId:
						context.activeSectionId === payload.section_id ? null : context.activeSectionId,
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'blocked_by_required_media',
						reason: payload.reason,
						slot_ids: payload.slot_ids
					})
				},
				terminal: null
			};
		}
		case 'section_partial': {
			if (!context.document) return { next: context, terminal: null };
			const payload = JSON.parse(data) as SectionPartialEvent;
			const result = applySectionPartial(context.document, payload);
			return {
				next: {
					...context,
					document: result.document,
					viewerWarning: result.warning?.message ?? context.viewerWarning,
					activeSectionId: payload.section_id,
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'partially_ready'
					})
				},
				terminal: null
			};
		}
		case 'section_asset_pending': {
			if (!context.document) return { next: context, terminal: null };
			const payload = JSON.parse(data) as SectionAssetPendingEvent;
			return {
				next: {
					...context,
					document: applySectionAssetPending(context.document, payload),
					activeSectionId: payload.section_id,
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'partially_ready'
					})
				},
				terminal: null
			};
		}
		case 'section_asset_ready': {
			if (!context.document) return { next: context, terminal: null };
			const payload = JSON.parse(data) as SectionAssetReadyEvent;
			return {
				next: {
					...context,
					document: applySectionAssetReady(context.document, payload),
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'partially_ready'
					})
				},
				terminal: null
			};
		}
		case 'section_final': {
			if (!context.document) return { next: context, terminal: null };
			const payload = JSON.parse(data) as SectionFinalEvent;
			return {
				next: {
					...context,
					document: applySectionFinal(context.document, payload),
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'partially_ready'
					})
				},
				terminal: null
			};
		}
		case 'section_ready': {
			if (!context.document) return { next: context, terminal: null };
			const payload = JSON.parse(data) as SectionReadyEvent;
			const result = applySectionReady(context.document, payload);
			return {
				next: {
					...context,
					document: result.document,
					plannedSections: payload.total_sections,
					viewerWarning: result.warning?.message ?? context.viewerWarning,
					activeSectionId:
						context.activeSectionId === payload.section_id ? null : context.activeSectionId,
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'ready'
					})
				},
				terminal: null
			};
		}
		case 'section_failed': {
			if (!context.document) return { next: context, terminal: null };
			const payload = JSON.parse(data) as SectionFailedEvent;
			return {
				next: {
					...context,
					document: applySectionFailed(context.document, payload),
					activeSectionId:
						context.activeSectionId === payload.section_id ? null : context.activeSectionId,
					sectionSignals: setSectionSignal(context.sectionSignals, payload.section_id, {
						status: 'failed'
					})
				},
				terminal: null
			};
		}
		case 'qc_complete': {
			const payload = JSON.parse(data) as QCCompleteEvent;
			return {
				next: {
					...context,
					qcSummary: { passed: payload.passed, total: payload.total }
				},
				terminal: null
			};
		}
		case 'complete':
			return { next: context, terminal: { kind: 'complete' } };
		case 'generation_failed': {
			const payload = JSON.parse(data) as { message: string };
			return {
				next: context,
				terminal: { kind: 'generation_failed', message: payload.message }
			};
		}
		case 'error': {
			const payload = JSON.parse(data) as ErrorEvent;
			return {
				next: context,
				terminal: { kind: 'error', message: payload.message }
			};
		}
		case 'component_ready':
		case 'visual_ready':
		case 'component_patched':
		case 'generation_started':
		case 'draft_pack_ready':
		case 'generation_complete':
		case 'work_orders_compiled': {
			const payload = JSON.parse(data) as Record<string, unknown>;
			const label =
				payload.component_id ??
				payload.visual_id ??
				payload.generation_id ??
				type;
			return {
				next: {
					...context,
					viewerWarning: `v3 stream: ${String(type)} → ${String(label)}`
				},
				terminal: null
			};
		}
		default:
			return { next: context, terminal: null };
	}
}
