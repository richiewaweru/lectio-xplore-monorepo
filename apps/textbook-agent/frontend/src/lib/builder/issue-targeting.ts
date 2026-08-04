import { getFieldComponentMap, type LessonDocument } from 'lectio';

import { isAiGeneratableComponent } from '$lib/builder/components/ai/ai-block-utils';
import type { BuilderIssue } from '$lib/builder/issues';

const VISUAL_MISMATCH_QUESTION_INSTRUCTION =
	'This question refers to a visual, but no diagram was planned for this section. Rewrite the question so it stands on its own without referring to a diagram.';

function sectionBlockIds(document: LessonDocument, sectionId: string): string[] {
	return document.sections.find((section) => section.id === sectionId)?.block_ids ?? [];
}

function sectionRefMatches(reference: string, sectionId: string): boolean {
	return (
		reference === sectionId ||
		reference.startsWith(`${sectionId}.`) ||
		reference.replace(/\d+$/, '') === sectionId
	);
}

function componentTarget(issue: BuilderIssue, sectionId: string): string | null {
	const repairMatch = issue.repair_target_id?.match(/^component:([^:]+):(.+)$/);
	if (repairMatch?.[1] && sectionRefMatches(repairMatch[1], sectionId)) {
		return repairMatch[2] ?? null;
	}

	const atMatch = issue.component_ref?.match(/^(.+)@([^@]+)$/);
	if (atMatch?.[2] && sectionRefMatches(atMatch[2], sectionId)) return atMatch[1] ?? null;

	const colonMatch = issue.component_ref?.match(/^([^:]+):(.+)$/);
	if (colonMatch?.[1] && sectionRefMatches(colonMatch[1], sectionId)) {
		return colonMatch[2] ?? null;
	}
	return null;
}

function generatedComponentTarget(issue: BuilderIssue, sectionId: string): string | null {
	if (!issue.generated_ref) return null;
	const [generatedSection, field] = issue.generated_ref.split('.');
	if (!generatedSection || !field || !sectionRefMatches(generatedSection, sectionId)) return null;
	const fieldComponentMap = getFieldComponentMap() as Record<string, string | undefined>;
	return fieldComponentMap[field] ?? null;
}

function uniqueAiBlockForComponent(
	document: LessonDocument,
	blockIds: string[],
	componentId: string
): string | undefined {
	const matches = blockIds.filter(
		(id) =>
			document.blocks[id]?.component_id === componentId &&
			isAiGeneratableComponent(componentId)
	);
	return matches.length === 1 ? matches[0] : undefined;
}

export function qcReasonToInstruction(issue: BuilderIssue): string {
	if (issue.kind === 'visual_mismatch' && issue.repair_target_id?.startsWith('questions:')) {
		return VISUAL_MISMATCH_QUESTION_INSTRUCTION;
	}
	return issue.message;
}

export function resolveTextIssueTarget(
	document: LessonDocument,
	sectionId: string,
	issue: BuilderIssue
): string | undefined {
	const blockIds = sectionBlockIds(document, sectionId);
	if (
		issue.target_block_id &&
		blockIds.includes(issue.target_block_id) &&
		isAiGeneratableComponent(document.blocks[issue.target_block_id]?.component_id ?? '')
	) {
		return issue.target_block_id;
	}

	const componentId = componentTarget(issue, sectionId) ?? generatedComponentTarget(issue, sectionId);
	if (componentId) {
		return uniqueAiBlockForComponent(document, blockIds, componentId);
	}
	return undefined;
}

export function resolveVisualIssueTarget(
	document: LessonDocument,
	sectionId: string,
	requested?: string
): string | undefined {
	const blockIds = sectionBlockIds(document, sectionId);
	if (requested && blockIds.includes(requested)) return requested;
	return blockIds.find((id) => {
		const componentId = document.blocks[id]?.component_id ?? '';
		return componentId.includes('diagram') || componentId.includes('image');
	});
}
