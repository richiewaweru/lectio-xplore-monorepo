import {
	orderedDocumentSections,
	toSectionContents,
	withDefaultLearnerSectionMeta,
	type DocumentSection,
	type LessonDocument
} from '@lectio/learn';

export interface StudentStage {
	section: DocumentSection;
	index: number;
	label: string;
	assessment_mode: NonNullable<DocumentSection['assessment_mode']>;
	required: boolean;
}

/** Build ordered student stages from an authored LessonDocument (no runtime state). */
export function buildStudentStages(document: LessonDocument): StudentStage[] {
	return orderedDocumentSections(document).map((raw, index) => {
		const section = withDefaultLearnerSectionMeta(raw);
		return {
			section,
			index,
			label: section.learner_label ?? section.title,
			assessment_mode: section.assessment_mode ?? 'ungraded-info',
			required: section.required ?? true
		};
	});
}

export function sectionContentAt(document: LessonDocument, sectionId: string) {
	const contents = toSectionContents(document);
	return contents.find((s) => s.section_id === sectionId) ?? null;
}

export function clampStageIndex(index: number, length: number): number {
	if (length <= 0) return 0;
	return Math.max(0, Math.min(index, length - 1));
}
