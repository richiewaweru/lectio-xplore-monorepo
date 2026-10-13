export interface NextLessonInfo {
	state: 'ready' | 'pending' | null;
	title?: string | null;
	instance_id?: string | null;
	/** 1-based lesson number, for "Lesson N is ready". */
	number?: number | null;
}

/** `topic` object on GET /api/v1/learn/instances/{id}; null for unlinked releases. */
export interface InstanceTopic {
	unit_id: string;
	title: string;
	lesson_position: number;
	lessons_total: number;
	next_lesson: { state: 'ready' | 'pending' | null; title: string | null; instance_id: string | null };
}

export function nextLessonFromTopic(topic: InstanceTopic | null | undefined): NextLessonInfo | null {
	if (!topic) return null;
	return { ...topic.next_lesson, number: topic.lesson_position + 1 };
}
