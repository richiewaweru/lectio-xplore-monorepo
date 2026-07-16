import type { LessonDocument } from 'lectio';

import { exportToLessonDocument } from '$lib/generation/export-document';
import {
	adaptV3PackToLectioDocument,
	type AdaptV3PackOptions,
	type V3PackDocument
} from '$lib/studio/v3-pack-to-lectio-document';
import type { BuilderIssue, IssueSection } from '$lib/builder/issues';

function record(value: unknown): Record<string, unknown> | null {
	return typeof value === 'object' && value !== null && !Array.isArray(value)
		? (value as Record<string, unknown>) : null;
}

function diagnosticIssues(pack: V3PackDocument, sectionId: string): BuilderIssue[] {
	const issues: BuilderIssue[] = [];
	for (const [index, value] of (pack.section_diagnostics ?? []).entries()) {
		const item = record(value);
		if (!item || item.section_id !== sectionId || item.status === 'complete') continue;
		const missingComponents = Array.isArray(item.missing_components) ? item.missing_components : [];
		const missingVisuals = Array.isArray(item.missing_visuals) ? item.missing_visuals : [];
		const warnings = Array.isArray(item.warnings) ? item.warnings.filter((v): v is string => typeof v === 'string') : [];
		const kind = missingVisuals.length ? 'visual_missing' : 'component_missing';
		issues.push({
			id: `section-diagnostic:${sectionId}:${index}`,
			severity: item.renderable === false ? 'blocking' : 'major',
			message: warnings.join(' ') || `Section ${sectionId} is incomplete.`,
			kind,
			component_ref: typeof missingComponents[0] === 'string' ? `${missingComponents[0]}@${sectionId}` : undefined,
			visual_id: typeof missingVisuals[0] === 'string' ? missingVisuals[0] : undefined,
			resolved: false
		});
	}
	for (const [index, value] of (pack.booklet_issues ?? []).entries()) {
		const item = record(value);
		if (!item) continue;
		const target = String(item.section_id ?? item.generated_ref ?? '');
		if (target !== sectionId) continue;
		issues.push({
			id: String(item.issue_id ?? `booklet-issue:${sectionId}:${index}`),
			severity: String(item.severity ?? 'major'),
			message: String(item.message ?? 'Generation issue requires review.'),
			kind: String(item.kind ?? item.category ?? 'generation_issue'),
			target_block_id: typeof item.target_block_id === 'string' ? item.target_block_id : undefined,
			component_ref: typeof item.component_ref === 'string' ? item.component_ref : undefined,
			visual_id: typeof item.visual_id === 'string' ? item.visual_id : undefined,
			resolved: false
		});
	}
	return issues;
}

export function v3PackToBuilderDocument(
	pack: V3PackDocument,
	options: AdaptV3PackOptions = {}
): LessonDocument {
	const generationDoc = adaptV3PackToLectioDocument(pack, options);
	const lesson = exportToLessonDocument(generationDoc);
	return {
		...lesson,
		sections: lesson.sections.map((section) => {
			const issues = diagnosticIssues(pack, section.id);
			return issues.length ? ({ ...section, meta: { issues } } as IssueSection) : section;
		})
	};
}
