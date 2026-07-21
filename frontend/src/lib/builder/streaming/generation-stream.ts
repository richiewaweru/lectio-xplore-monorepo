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
	const planPositions = new Map(plan.map((section) => [section.id, section.position]));
	const localSections = new Map(local.sections.map((section) => [section.id, section]));
	const nextSections = [...local.sections];
	const nextBlocks = { ...local.blocks };
	let changed = false;

	for (const adaptedSection of adapted.sections) {
		const existingSection = localSections.get(adaptedSection.id);
		if (!existingSection) {
			const insertedSection = {
				...adaptedSection,
				position: planPositions.get(adaptedSection.id) ?? adaptedSection.position
			};
			nextSections.push(insertedSection);
			for (const blockId of insertedSection.block_ids) {
				const block = adapted.blocks[blockId];
				if (block) nextBlocks[blockId] = block;
			}
			changed = true;
			continue;
		}

		const existingComponentCounts = new Map<string, number>();
		let nextPosition = 0;
		for (const blockId of existingSection.block_ids) {
			const block = local.blocks[blockId];
			if (!block) continue;
			existingComponentCounts.set(
				block.component_id,
				(existingComponentCounts.get(block.component_id) ?? 0) + 1
			);
			nextPosition = Math.max(nextPosition, block.position + 1);
		}

		const adaptedComponentCounts = new Map<string, number>();
		const appendedBlockIds: string[] = [];
		for (const blockId of adaptedSection.block_ids) {
			const block = adapted.blocks[blockId];
			if (!block) continue;
			const occurrence = adaptedComponentCounts.get(block.component_id) ?? 0;
			adaptedComponentCounts.set(block.component_id, occurrence + 1);
			if (occurrence < (existingComponentCounts.get(block.component_id) ?? 0)) continue;
			nextBlocks[blockId] = { ...block, position: nextPosition++ };
			appendedBlockIds.push(blockId);
		}

		if (appendedBlockIds.length > 0) {
			const sectionIndex = nextSections.findIndex((section) => section.id === existingSection.id);
			nextSections[sectionIndex] = {
				...existingSection,
				block_ids: [...existingSection.block_ids, ...appendedBlockIds]
			};
			changed = true;
		}
	}

	if (!changed) return local;

	return {
		...local,
		sections: nextSections,
		blocks: nextBlocks,
		updated_at: new Date().toISOString()
	};
}

export function isTerminalPackStatus(status: unknown): boolean {
	return status === 'final_ready' || status === 'final_with_warnings' || status === 'failed_unusable';
}

export function isTerminalGenerationDocument(pack: {
	status?: unknown;
	progress?: { stage?: unknown };
}): boolean {
	const stage = pack.progress?.stage;
	return isTerminalPackStatus(pack.status) || stage === 'completed' || stage === 'failed';
}
