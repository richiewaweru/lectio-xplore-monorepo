import type { ArtifactProgress, ArtifactProgressStep } from '$lib/types/units';

export interface ProgressStepView {
	key: string;
	label: string;
	/** "(n/N)" suffix when counts are known, else ''. */
	counts: string;
	marker: ArtifactProgressStep['status'];
}

export interface FailedFigureView {
	id: string;
	sectionTitle: string;
	summary: string;
	retryable: boolean;
}

export interface LessonProgressView {
	steps: ProgressStepView[];
	currentLabel: string | null;
	startedAt: number | null;
	figuresLine: string | null;
	failedFigures: FailedFigureView[];
	labelWarnings: string[];
}

export const PROGRESS_NOTE =
	'This usually takes a few minutes. You can leave this page; we’ll keep working.';

export function progressView(
	progress: ArtifactProgress | null | undefined
): LessonProgressView | null {
	if (!progress || !progress.steps?.length) return null;
	const steps = progress.steps.map((step) => ({
		key: step.key,
		label: step.label,
		counts: step.total ? `(${step.done ?? 0}/${step.total})` : '',
		marker: step.status
	}));
	const parsed = progress.started_at ? parseUtc(progress.started_at) : NaN;
	const planned = progress.figures_planned ?? 0;
	const ready = progress.figures_ready ?? 0;
	const failed = progress.figures_failed ?? 0;
	const figures = progress.figures ?? [];
	return {
		steps,
		currentLabel: progress.current_label ?? null,
		startedAt: Number.isFinite(parsed) ? parsed : null,
		figuresLine:
			planned + ready + failed > 0 ? `Figures: ${ready} ready / ${failed} failed / ${planned} planned` : null,
		failedFigures: figures
			.filter((figure) => figure.status === 'failed')
			.map((figure) => ({
				id: figure.figure_id,
				sectionTitle: figure.section_title || figure.section_id || 'A section',
				summary: figure.error_summary || 'The figure could not be created.',
				retryable: figure.retryable === true
			})),
		labelWarnings: figures.flatMap((figure) => figure.warnings ?? []).filter(Boolean)
	};
}

/** Parse an ISO timestamp; a string with no offset/Z is treated as UTC, not local time. */
export function parseUtc(value: string): number {
	const trimmed = value.trim();
	const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(trimmed);
	const hasTime = trimmed.includes('T') || trimmed.includes(' ');
	return Date.parse(hasZone || !hasTime ? trimmed : `${trimmed.replace(' ', 'T')}Z`);
}

export function autoRetryText(
	autoRetry: { attempt: number | null; maxAttempts: number | null } | null | undefined
): string | null {
	if (!autoRetry) return null;
	return autoRetry.attempt && autoRetry.maxAttempts
		? `Retrying automatically (attempt ${autoRetry.attempt} of ${autoRetry.maxAttempts}).`
		: 'Retrying automatically.';
}

/** "2m 05s"-style elapsed text; clamps negative clock skew to 0. */
export function formatElapsed(startedAt: number | null, nowMs: number): string | null {
	if (startedAt === null) return null;
	const total = Math.max(0, Math.floor((nowMs - startedAt) / 1000));
	const minutes = Math.floor(total / 60);
	const seconds = total % 60;
	return minutes > 0 ? `${minutes}m ${String(seconds).padStart(2, '0')}s` : `${seconds}s`;
}
