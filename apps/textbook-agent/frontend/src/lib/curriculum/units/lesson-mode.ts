import type { LessonMode } from '$lib/types/units';

const LESSON_MODES: readonly LessonMode[] = [
	'first_exposure',
	'consolidation',
	'repair',
	'retrieval',
	'transfer'
];

const LABELS: Record<LessonMode, string> = {
	first_exposure: 'First exposure',
	consolidation: 'Consolidation',
	repair: 'Repair',
	retrieval: 'Retrieval',
	transfer: 'Transfer'
};

export function isLessonMode(value: unknown): value is LessonMode {
	return typeof value === 'string' && (LESSON_MODES as readonly string[]).includes(value);
}

/** The lesson's stored mode when valid, otherwise first exposure. */
export function effectiveLessonMode(
	lesson: { lesson_mode?: string | null } | null | undefined
): LessonMode {
	const stored = lesson?.lesson_mode;
	return isLessonMode(stored) ? stored : 'first_exposure';
}

export function lessonModeLabel(mode: LessonMode): string {
	return LABELS[mode];
}

/** Quiet "Consolidation: reason" line; null unless both a valid stored mode and a reason exist. */
export function lessonModeNote(
	lesson: { lesson_mode?: string | null; lesson_mode_reason?: string | null } | null | undefined
): string | null {
	const reason = lesson?.lesson_mode_reason?.trim();
	if (!lesson || !isLessonMode(lesson.lesson_mode) || !reason) return null;
	return `${LABELS[lesson.lesson_mode]}: ${reason}`;
}
