import { toSectionContents, validateSection, type LessonDocument } from 'lectio';

/** Warnings from `validateSection` for the section that contains `blockId`. */
export function validationWarningsForBlock(doc: LessonDocument, blockId: string): string[] {
	const sec = doc.sections.find((s) => s.block_ids.includes(blockId));
	if (!sec) return [];
	const contents = toSectionContents(doc);
	const shell = contents.find((c) => c.section_id === sec.id);
	if (!shell) return [];
	return validateSection(shell);
}
