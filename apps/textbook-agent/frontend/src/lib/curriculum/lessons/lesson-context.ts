/** Canonical Unit lesson workspace projection helpers. */
import type {
	ArtifactPath,
	ArtifactUiState,
	LessonArtifactUi,
	PreparedLessonStatus,
	PreparationWorkspaceState,
	WorkspaceStateError
} from '$lib/types/units';

export type LessonPrepUiState = 'not_prepared' | 'preparing' | 'awaiting_review' | 'ready' | 'needs_attention';

// Backend error codes whose raw `message` is written for logs/support, not
// for a teacher. Map the ones seen in the wild to plain language; anything
// else falls back to the backend's message as-is.
const FRIENDLY_ERROR_MESSAGES: Record<string, string> = {
	// P12A: the orphan reaper marks a crashed/unobservable stage-2 pipeline
	// task this way. Always retryable -- the raw message ("... no longer
	// observable (owner_boot_id=...)") is debugging detail, not something a
	// teacher should have to parse.
	PIPELINE_ORPHANED:
		'Lesson preparation was interrupted (its process stopped unexpectedly). It is safe to retry.',
	LEGACY_STAGE_RETIRED:
		'This generation is parked at a pre-P11B execution stage that no longer runs. It cannot resume automatically and needs attention.'
};

/** Prefer a known-friendly message for the error's code; fall back to the
 * backend's own message, then a generic default. */
export function preparationErrorMessage(error: WorkspaceStateError | null | undefined): string {
	const code = error?.code ?? null;
	if (code && FRIENDLY_ERROR_MESSAGES[code]) return FRIENDLY_ERROR_MESSAGES[code];
	return error?.message ?? 'Lesson preparation failed unexpectedly.';
}

export function lessonWorkspaceHref(
	unitId: string,
	lessonId: string,
	tab: 'plan' | 'learn' | 'print' = 'plan'
): string {
	return `/units/${encodeURIComponent(unitId)}/lessons/${encodeURIComponent(lessonId)}/${tab}`;
}

export function canonicalPreparationState(
	status: PreparedLessonStatus | null | undefined
): PreparationWorkspaceState | 'legacy_ambiguous' {
	const prep = status?.workspace?.preparation;
	if (prep) return prep.state;
	return status ? 'legacy_ambiguous' : 'not_started';
}

export function preparationIsApprovedAndFresh(status: PreparedLessonStatus | null | undefined): boolean {
	const prep = status?.workspace?.preparation;
	return Boolean(
		prep?.state === 'approved' &&
		prep.approved_snapshot_verified === true &&
		!prep.stale &&
		!status?.stale
	);
}

export function preparationUiState(status: PreparedLessonStatus | null | undefined): LessonPrepUiState {
	switch (canonicalPreparationState(status)) {
		case 'not_started': return 'not_prepared';
		case 'planning': return 'preparing';
		case 'awaiting_review': return 'awaiting_review';
		case 'approved': return preparationIsApprovedAndFresh(status) ? 'ready' : 'needs_attention';
		default: return 'needs_attention';
	}
}

export function preparationLabel(state: LessonPrepUiState): string {
	switch (state) {
		case 'not_prepared': return 'Not prepared';
		case 'preparing': return 'Preparing';
		case 'awaiting_review': return 'Awaiting review';
		case 'ready': return 'Approved';
		case 'needs_attention': return 'Needs attention';
	}
}

export function badgeToneForPrep(state: LessonPrepUiState): 'neutral' | 'ready' | 'attention' | 'info' {
	switch (state) {
		case 'ready': return 'ready';
		case 'needs_attention': return 'attention';
		case 'preparing': case 'awaiting_review': return 'info';
		default: return 'neutral';
	}
}

function hrefId(href: string | null | undefined, pattern: RegExp): string | null {
	const match = href?.match(pattern);
	return match?.[1] ? decodeURIComponent(match[1]) : null;
}

/** Return only identities carried by the canonical path projection. */
export function resolveBuilderLessonId(status: PreparedLessonStatus | null | undefined): string | null {
	const learn = status?.workspace?.learn;
	return hrefId(learn?.open_href, /\/builder\/from-native-learn\/([^/?#]+)/) ??
		hrefId(learn?.open_href, /\/builder\/([^/?#]+)/);
}

export function resolvePrintGenerationId(status: PreparedLessonStatus | null | undefined): string | null {
	const print = status?.workspace?.print;
	return print?.output_id ?? hrefId(print?.open_href, /\/(?:studio\/print|studio\/generations)\/([^/?#]+)/);
}

export function lessonArtifactUi(
	status: PreparedLessonStatus | null | undefined,
	path: ArtifactPath,
	loadError?: string | null
): LessonArtifactUi {
	const workspace = status?.workspace?.[path];
	if (!workspace) {
		return {
			path, exists: false, state: status ? 'needs_attention' : 'not_created',
			realizationId: null, outputId: null, openHref: null,
			errorSummary: loadError ?? (status ? 'Path status is ambiguous. Refresh the lesson workspace.' : null),
			retryable: false, recoveryAction: status ? 'reload_lesson' : null, legacyAmbiguous: Boolean(status),
			sharedDocumentState: null
		};
	}
	const canonicalState = workspace.state;
	// `needs_review` is authoritative from the backend: a pinned SharedLessonDocument
	// awaiting a human review decision. Never infer this from output_id/hash alone.
	const state: ArtifactUiState = canonicalState === 'needs_review'
		? 'needs_review'
		: canonicalState === 'queued' || canonicalState === 'running'
			? 'preparing'
			: canonicalState === 'ready'
				? 'ready'
				: canonicalState === 'failed_recoverable'
					? 'failed'
					: canonicalState === 'failed_terminal'
						? 'needs_attention'
						: 'not_created';
	return {
		path,
		exists: canonicalState !== 'not_created',
		state,
		realizationId: workspace.realization_id ?? null,
		outputId: workspace.output_id ?? null,
		openHref: workspace.open_href ?? null,
		// Preview-fetch failures are displayed separately and cannot turn a ready
		// realization into a failed/retryable run.
		errorSummary: workspace.error?.message ?? loadError ?? null,
		// needs_review never advertises a retry action: the backend has no retry
		// endpoint for a pending human review, and offering one would be retry spam.
		retryable: state !== 'needs_review' && canonicalState === 'failed_recoverable' && workspace.error?.retryable === true && !workspace.stale && !workspace.legacy_ambiguous,
		recoveryAction: state === 'needs_review' ? null : (workspace.error?.recovery_action ?? null),
		legacyAmbiguous: Boolean(workspace.legacy_ambiguous),
		sharedDocumentState: workspace.shared_document_state ?? null
	};
}

export function resolvePlanGenerationId(status: PreparedLessonStatus | null | undefined): string | null {
	return status?.workspace?.preparation?.generation_id ?? null;
}
