import type { LessonDocument } from 'lectio';

import { exportToLessonDocument } from '$lib/generation/export-document';
import {
	adaptV3PackToLectioDocument,
	type AdaptV3PackOptions,
	type V3PackDocument
} from '$lib/studio/v3-pack-to-lectio-document';
import type { IssueSection } from '$lib/builder/issues';
import { partitionGenerationIssues } from '$lib/builder/generation-issues';

export { partitionGenerationIssues } from '$lib/builder/generation-issues';
export type { GenerationIssuePartition } from '$lib/builder/generation-issues';

export function v3PackToBuilderDocument(
	pack: V3PackDocument,
	options: AdaptV3PackOptions = {}
): LessonDocument {
	const generationDoc = adaptV3PackToLectioDocument(pack, options);
	const lesson = exportToLessonDocument(generationDoc);
	const { sectionIssues } = partitionGenerationIssues(pack, lesson.sections.map((section) => section.id));
	return {
		...lesson,
		sections: lesson.sections.map((section) => {
			const issues = sectionIssues[section.id] ?? [];
			return issues.length ? ({ ...section, meta: { issues } } as IssueSection) : section;
		})
	};
}
