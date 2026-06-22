import type {
	CanvasSection,
	SectionAssemblyDiagnostic,
	V3StructuralPlanSection
} from '$lib/types/v3';

function normalizeTitle(section: Record<string, unknown>, fallbackId: string): string {
	const header =
		typeof section.header === 'object' && section.header !== null
			? (section.header as Record<string, unknown>)
			: null;
	const headerTitle = typeof header?.title === 'string' ? header.title : '';
	return headerTitle || fallbackId;
}

function plannedOrder(sectionId: string, plannedSections: V3StructuralPlanSection[]): number | null {
	const index = plannedSections.findIndex((section) => section.id === sectionId);
	return index >= 0 ? index : null;
}

export function mapPackSectionsToCanvas(
	sections: unknown[],
	diagnostics: SectionAssemblyDiagnostic[] = [],
	plannedSections: V3StructuralPlanSection[] = []
): CanvasSection[] {
	const diagnosticsBySectionId = new Map(
		diagnostics.map((diagnostic) => [diagnostic.section_id, diagnostic] as const)
	);

	const packedSections: CanvasSection[] = sections.map((raw, index) => {
		const section = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {};
		const sectionId = String(section.section_id ?? `section-${index + 1}`);
		const diagnostic = diagnosticsBySectionId.get(sectionId);
		return {
			id: sectionId,
			title: normalizeTitle(section, sectionId),
			teacher_labels: '',
			order: plannedOrder(sectionId, plannedSections) ?? index,
			sectionStatus: diagnostic?.status ?? 'complete',
			stage2Preview: null,
			renderable: diagnostic?.renderable ?? true,
			missingComponents: diagnostic?.missing_components ?? [],
			missingVisuals: diagnostic?.missing_visuals ?? [],
			diagnosticWarnings: diagnostic?.warnings ?? [],
			components: [],
			visual: null,
			questions: [],
			mergedFields: section
		};
	});

	const packedIds = new Set(packedSections.map((section) => section.id));
	const diagnosticOnlySections: CanvasSection[] = diagnostics
		.filter((diagnostic) => !packedIds.has(diagnostic.section_id))
		.map((diagnostic, index) => {
			const planned = plannedSections.find((section) => section.id === diagnostic.section_id);
			return {
				id: diagnostic.section_id,
				title: planned?.title ?? diagnostic.section_id,
				teacher_labels: planned?.role ?? '',
				order: plannedOrder(diagnostic.section_id, plannedSections) ?? packedSections.length + index,
				sectionStatus: diagnostic.status,
				stage2Preview: null,
				renderable: diagnostic.renderable,
				missingComponents: diagnostic.missing_components,
				missingVisuals: diagnostic.missing_visuals,
				diagnosticWarnings: diagnostic.warnings,
				components: [],
				visual: null,
				questions: [],
				mergedFields: {
					section_id: diagnostic.section_id,
					header: {
						title: planned?.title ?? diagnostic.section_id
					}
				}
			};
		});

	return [...packedSections, ...diagnosticOnlySections].sort((left, right) => left.order - right.order);
}
