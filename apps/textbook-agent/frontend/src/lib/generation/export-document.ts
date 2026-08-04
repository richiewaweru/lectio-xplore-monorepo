import { fromSectionContents, type LessonDocument } from 'lectio';

import type { GenerationDocument } from '$lib/types';

/**
 * Convert a completed generation to the portable Lesson Builder interchange format.
 */
export function exportToLessonDocument(doc: GenerationDocument): LessonDocument {
	const title = doc.sections[0]?.header?.title?.trim() || doc.subject;
	const base = fromSectionContents(doc.sections, {
		title,
		subject: doc.subject,
		preset_id: doc.preset_id,
		template_id: doc.template_id,
		source: 'generated',
		source_generation_id: doc.generation_id
	});
	return {
		...base,
		description: doc.context || undefined
	};
}

/**
 * Trigger a JSON download of a LessonDocument (`.lesson.json`).
 */
export function downloadLessonDocument(lesson: LessonDocument): void {
	const json = JSON.stringify(lesson, null, 2);
	const blob = new Blob([json], { type: 'application/json' });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = `${slugify(lesson.title)}.lesson.json`;
	a.click();
	URL.revokeObjectURL(url);
}

function slugify(text: string): string {
	return text
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-|-$/g, '') || 'lesson';
}
