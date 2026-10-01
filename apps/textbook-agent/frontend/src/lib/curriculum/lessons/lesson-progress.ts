import type { ArtifactProgress, ArtifactProgressStep } from '$lib/types/units';

export interface ProgressStepView {
	key: string;
	label: string;
	/** "(n/N)" suffix when counts are known, else ''. */
	counts: string;
	marker: ArtifactProgressStep['status'];
}

export interface LessonProgressView {
	steps: ProgressStepView[];
	currentLabel: string | null;
	startedAt: number | null;
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
	const parsed = progress.started_at ? Date.parse(progress.started_at) : NaN;
	return {
		steps,
		currentLabel: progress.current_label ?? null,
		startedAt: Number.isFinite(parsed) ? parsed : null
	};
}

/** "2m 05s"-style elapsed text; clamps negative clock skew to 0. */
export function formatElapsed(startedAt: number | null, nowMs: number): string | null {
	if (startedAt === null) return null;
	const total = Math.max(0, Math.floor((nowMs - startedAt) / 1000));
	const minutes = Math.floor(total / 60);
	const seconds = total % 60;
	return minutes > 0 ? `${minutes}m ${String(seconds).padStart(2, '0')}s` : `${seconds}s`;
}
