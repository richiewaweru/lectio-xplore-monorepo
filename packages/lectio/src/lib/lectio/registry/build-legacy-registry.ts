import type { ComponentMeta } from '$lib/schema/component-meta';
import type { SectionContent } from '$lib/schema/types';
import type { LectioContentModule } from '$lib/lectio/core/types';
import { teacherFor } from '$lib/teacher/teacher-facing';

export function defaultGenerationHint(component: ComponentMeta): string {
	const field = component.sectionField ?? 'section';
	return `Generate ${field} content that ${component.purpose.toLowerCase()}. Prioritize ${component.cognitiveJob.toLowerCase()} with concise, learner-ready wording.`;
}

/**
 * Produces legacy `componentRegistry`-shaped maps from Lectio modules.
 * Mirrors the module-load normalization that previously ran in `registry.ts`.
 */
export function applyGenerationHintNormalization(registry: Record<string, ComponentMeta>): void {
	for (const component of Object.values(registry)) {
		if (component.sectionField === null) continue;
		const hint = component.generationHint?.trim();
		component.generationHint = hint && hint.length > 0 ? hint : defaultGenerationHint(component);
		if (!component.generationHint?.trim()) {
			throw new Error(
				`[Lectio] Missing generationHint for mapped component "${component.id}" (${component.sectionField}).`
			);
		}
	}
}

export function buildLegacyComponentRegistryFromModules(
	modules: readonly LectioContentModule[]
): Record<string, ComponentMeta> {
	const out: Record<string, ComponentMeta> = {};
	for (const mod of modules) {
		const t = teacherFor(mod.metadata.id);
		const meta: ComponentMeta = {
			id: mod.metadata.id,
			...t,
			teachingIntent: mod.metadata.teachingIntent,
			name: mod.metadata.name,
			purpose: mod.metadata.role,
			cognitiveJob: mod.metadata.cognitiveJob,
			subjects: [...mod.metadata.subjects],
			behaviourModes: [...mod.metadata.behaviourModes],
			shadcnPrimitive: mod.metadata.shadcnPrimitive,
			capacity: { ...mod.metadata.capacity },
			printFallback: mod.print?.fallback,
			web: mod.web,
			generationHint: mod.metadata.generationHint,
			status: mod.metadata.status,
			group: mod.metadata.phase,
			sectionField: mod.metadata.sectionField as keyof SectionContent | null
		};
		out[mod.metadata.registryKey] = meta;
	}

	applyGenerationHintNormalization(out);
	return out;
}
