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

export type GenerationIssuePartition = {
	sectionIssues: Record<string, BuilderIssue[]>;
	documentLevelIssues: BuilderIssue[];
};

function targetMatchesSection(target: string, sectionId: string): boolean {
	return (
		target === sectionId ||
		target.startsWith(`${sectionId}.`) ||
		target.replace(/\d+$/, '') === sectionId
	);
}

function visualIdForIssue(item: Record<string, unknown>): string | undefined {
	if (typeof item.visual_id === 'string' && item.visual_id) return item.visual_id;
	const repairTarget = typeof item.repair_target_id === 'string' ? item.repair_target_id : '';
	return repairTarget.startsWith('visual:') ? repairTarget.slice('visual:'.length) : undefined;
}

function bookletIssue(item: Record<string, unknown>, target: string): BuilderIssue {
	const visualId = visualIdForIssue(item);
	const category = String(item.category ?? item.kind ?? 'generation_issue');
	const message = String(item.message ?? 'Generation issue requires review.');
	return {
		id: String(item.issue_id ?? `booklet-issue:${category}:${target || 'document'}:${message}`),
		severity: String(item.severity ?? 'major'),
		message,
		kind: category,
		target_block_id: typeof item.target_block_id === 'string' ? item.target_block_id : undefined,
		generated_ref: typeof item.generated_ref === 'string' ? item.generated_ref : undefined,
		component_ref: typeof item.component_ref === 'string' ? item.component_ref : undefined,
		visual_id: visualId,
		repair_target_id:
			typeof item.repair_target_id === 'string' ? item.repair_target_id : undefined,
		resolved: false
	};
}

export function partitionGenerationIssues(
	pack: V3PackDocument,
	sectionIds: string[]
): GenerationIssuePartition {
	const sectionIssues = Object.fromEntries(sectionIds.map((sectionId) => [sectionId, [] as BuilderIssue[]]));
	const documentLevelIssues: BuilderIssue[] = [];
	for (const [index, value] of (pack.section_diagnostics ?? []).entries()) {
		const item = record(value);
		const sectionId = typeof item?.section_id === 'string' ? item.section_id : '';
		if (!item || !sectionIssues[sectionId] || item.status === 'complete') continue;
		const missingComponents = Array.isArray(item.missing_components) ? item.missing_components : [];
		const missingVisuals = Array.isArray(item.missing_visuals) ? item.missing_visuals : [];
		const warnings = Array.isArray(item.warnings) ? item.warnings.filter((v): v is string => typeof v === 'string') : [];
		const kind = missingVisuals.length ? 'visual_missing' : 'component_missing';
		sectionIssues[sectionId].push({
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
		const visualId = visualIdForIssue(item);
		const visualTarget = visualId
			? pack.visual_blocks?.find((visual) => visual.visual_id === visualId)?.attaches_to ?? ''
			: '';
		const sectionId = sectionIds.find(
			(id) => targetMatchesSection(target, id) || targetMatchesSection(visualTarget, id)
		);
		const issue = bookletIssue(item, target || visualTarget || `unkeyed-${index}`);
		if (sectionId) sectionIssues[sectionId].push(issue);
		else documentLevelIssues.push(issue);
	}
	return { sectionIssues, documentLevelIssues };
}

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
