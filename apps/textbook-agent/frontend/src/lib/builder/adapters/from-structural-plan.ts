import type { LessonDocument } from 'lectio';

import type { V3StructuralPlan } from '$lib/types/v3';

export function v3StructuralPlanToBuilderDocument(
	plan: V3StructuralPlan,
	options: {
		generationId: string;
		title: string;
		templateId?: string;
		presetId?: string;
		subject?: string;
	}
): LessonDocument {
	const now = new Date().toISOString();
	return {
		version: 1,
		id: crypto.randomUUID(),
		title: options.title.trim() || plan.lesson_intent.goal,
		subject: options.subject ?? plan.lesson_intent.goal,
		preset_id: options.presetId ?? 'blue-classroom',
		source: 'generated',
		source_generation_id: options.generationId,
		sections: [],
		blocks: {},
		media: {},
		created_at: now,
		updated_at: now
	};
}
