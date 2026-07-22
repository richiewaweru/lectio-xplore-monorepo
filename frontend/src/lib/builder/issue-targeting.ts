import type { LessonDocument } from 'lectio';

import { isAiGeneratableComponent } from '$lib/builder/components/ai/ai-block-utils';
import type { BuilderIssue } from '$lib/builder/issues';

const QUESTION_COMPONENT_IDS = [
	'practice-stack',
	'quiz-check',
	'short-answer',
	'fill-in-blank',
	'student-textbox'
];

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

	const componentId = componentTarget(issue, sectionId);
	if (componentId) {
		return blockIds.find(
			(id) =>
				document.blocks[id]?.component_id === componentId &&
				isAiGeneratableComponent(componentId)
		);
	}

	const questionMatch = issue.repair_target_id?.match(/^questions:(.+)$/);
	if (questionMatch?.[1] && sectionRefMatches(questionMatch[1], sectionId)) {
		return blockIds.find((id) =>
			QUESTION_COMPONENT_IDS.includes(document.blocks[id]?.component_id ?? '')
		);
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
