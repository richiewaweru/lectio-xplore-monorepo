import type { LessonDocument } from 'lectio';

import type { V3StructuralPlan } from '$lib/types/v3';

export type PendingPlanSection = { id: string; title: string; position: number };

export function pendingPlanFromStructuralPlan(plan: V3StructuralPlan | null): PendingPlanSection[] {
	return (plan?.sections ?? []).map((section, position) => ({
		id: section.id,
		title: section.title,
		position
	}));
}

export function appendAbsentGenerationSections(
	local: LessonDocument,
	adapted: LessonDocument,
	plan: PendingPlanSection[]
): LessonDocument {
	const existingIds = new Set(local.sections.map((section) => section.id));
	const planPositions = new Map(plan.map((section) => [section.id, section.position]));
	const inserted = adapted.sections
		.filter((section) => !existingIds.has(section.id))
		.map((section) => ({
			...section,
			position: planPositions.get(section.id) ?? section.position
		}));

	if (inserted.length === 0) return local;

	const insertedBlockIds = new Set(inserted.flatMap((section) => section.block_ids));
	const insertedBlocks = Object.fromEntries(
		Object.entries(adapted.blocks).filter(([blockId]) => insertedBlockIds.has(blockId))
	);

	return {
		...local,
		sections: [...local.sections, ...inserted],
		blocks: { ...local.blocks, ...insertedBlocks },
		updated_at: new Date().toISOString()
	};
}

export function isTerminalPackStatus(status: unknown): boolean {
	return status === 'final_ready' || status === 'final_with_warnings' || status === 'failed_unusable';
}

export function allPlannedSectionsPresent(
	document: LessonDocument,
	plan: PendingPlanSection[]
): boolean {
	if (plan.length === 0) return false;
	const ids = new Set(document.sections.map((section) => section.id));
	return plan.every((section) => ids.has(section.id));
}
