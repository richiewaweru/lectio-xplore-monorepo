/**
 * Lesson workspace context — maps path lessons to Plan / Learn / Print destinations
 * without exposing internal IDs in teacher-facing copy.
 */
import type { PreparedLessonStatus } from '$lib/types/units';

export type LessonPrepUiState = 'not_prepared' | 'preparing' | 'ready' | 'needs_attention';

export function lessonWorkspaceHref(
	unitId: string,
	lessonId: string,
	tab: 'plan' | 'learn' | 'print' = 'plan'
): string {
	return `/units/${encodeURIComponent(unitId)}/lessons/${encodeURIComponent(lessonId)}/${tab}`;
}

export function preparationUiState(status: PreparedLessonStatus | null | undefined): LessonPrepUiState {
	if (!status || !status.generation_id) return 'not_prepared';
	if (status.stale) return 'needs_attention';
	const stage = (status.workflow_stage || status.generation_status || '').toLowerCase();
	if (stage.includes('fail') || stage === 'failed_terminal') return 'needs_attention';
	if (
		stage.includes('generat') ||
		stage.includes('pending') ||
		stage.includes('queued') ||
		stage.includes('running') ||
		stage.includes('prepar')
	) {
		return 'preparing';
	}
	const hasOutput =
		Boolean(status.print_open_href || status.learn_open_href || status.print_output_id || status.learn_output_id) ||
		(status.realizations?.length ?? 0) > 0;
	if (hasOutput || stage.includes('ready') || stage.includes('approved') || stage.includes('complete')) {
		return 'ready';
	}
	if (status.generation_id) return 'preparing';
	return 'not_prepared';
}

export function preparationLabel(state: LessonPrepUiState): string {
	switch (state) {
		case 'not_prepared':
			return 'Not prepared';
		case 'preparing':
			return 'Preparing';
		case 'ready':
			return 'Ready';
		case 'needs_attention':
			return 'Needs attention';
	}
}

export function badgeToneForPrep(
	state: LessonPrepUiState
): 'neutral' | 'ready' | 'attention' | 'info' {
	switch (state) {
		case 'ready':
			return 'ready';
		case 'needs_attention':
			return 'attention';
		case 'preparing':
			return 'info';
		default:
			return 'neutral';
	}
}

/** Extract builder lesson id from open href or learn_output_id when it looks like a builder id. */
export function resolveBuilderLessonId(status: PreparedLessonStatus | null | undefined): string | null {
	if (!status) return null;
	const href = status.learn_open_href;
	if (href) {
		const native = href.match(/\/builder\/from-native-learn\/([^/?#]+)/);
		if (native?.[1]) return decodeURIComponent(native[1]);
		const m = href.match(/\/builder\/([^/?#]+)/);
		if (m?.[1]) return decodeURIComponent(m[1]);
	}
	return null;
}

export function resolvePrintGenerationId(status: PreparedLessonStatus | null | undefined): string | null {
	if (!status) return null;
	if (status.print_output_id) return status.print_output_id;
	const href = status.print_open_href;
	if (href) {
		const m = href.match(/\/(?:studio\/print|studio\/generations)\/([^/?#]+)/);
		if (m?.[1]) return decodeURIComponent(m[1]);
	}
	if (status.generation_id && pathHasPrint(status)) return status.generation_id;
	return status.generation_id;
}

function pathHasPrint(status: PreparedLessonStatus): boolean {
	return Boolean(
		status.print_open_href || status.print_output_id || status.print_realization_id
	);
}

export function resolvePlanGenerationId(status: PreparedLessonStatus | null | undefined): string | null {
	return status?.generation_id ?? null;
}
