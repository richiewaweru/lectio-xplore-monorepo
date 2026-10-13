export type TopicLessonState = 'done' | 'current' | 'ready' | 'pending';

export interface TopicLesson {
	path_lesson_id: string;
	position: number;
	title: string;
	state: TopicLessonState;
	instance_id: string | null;
	release_id?: string | null;
	best_after_position: number | null;
	sections_done?: number;
	sections_total?: number;
}

export interface Topic {
	unit_id: string;
	title: string;
	summary?: string | null;
	class_id?: string;
	lessons_total: number;
	lessons_done: number;
	next_lesson_id: string | null;
	lessons: TopicLesson[];
}

export interface OtherLesson {
	instance_id: string;
	title: string;
	state: 'ready' | 'current' | 'done';
}

export interface TopicsResponse {
	learner_id?: string;
	display_name: string;
	code: string | null;
	topics: Topic[];
	other_lessons: OtherLesson[];
}

/** A lesson can be opened only when it has an instance and is not pending. */
export function isOpenable(lesson: TopicLesson): boolean {
	return lesson.state !== 'pending' && Boolean(lesson.instance_id);
}

export function progressPercent(topic: Pick<Topic, 'lessons_done' | 'lessons_total'>): number {
	if (!topic.lessons_total) return 0;
	return Math.min(100, Math.round((topic.lessons_done / topic.lessons_total) * 100));
}

export type TopicAction =
	| { kind: 'start' | 'continue' | 'view'; label: string; lesson: TopicLesson | null }
	| { kind: 'preparing'; label: string; lesson: null };

/** The card action per doc 38 section 8.2: Start, Continue: {title}, or View. */
export function topicAction(topic: Topic): TopicAction {
	const next = topic.lessons.find((l) => l.path_lesson_id === topic.next_lesson_id) ?? null;
	const allDone = topic.lessons_total > 0 && topic.lessons_done >= topic.lessons_total;
	if (allDone) return { kind: 'view', label: 'View', lesson: null };
	const started =
		topic.lessons_done > 0 ||
		topic.lessons.some((l) => l.state === 'current' || (l.sections_done ?? 0) > 0);
	if (next && isOpenable(next)) {
		return started
			? { kind: 'continue', label: `Continue: ${next.title}`, lesson: next }
			: { kind: 'start', label: 'Start', lesson: next };
	}
	if (started) return { kind: 'view', label: 'View', lesson: null };
	return { kind: 'preparing', label: 'Being prepared', lesson: null };
}

/** The lesson marked "you are here" on the roadmap. */
export function currentLessonId(topic: Topic): string | null {
	const current = topic.lessons.find((l) => l.state === 'current');
	return current?.path_lesson_id ?? topic.next_lesson_id ?? null;
}
