import { isBookletStatus } from '$lib/studio/v3-booklet';
import type { BookletStatus, V3DraftPack } from '$lib/types/v3';

function toStringArray(raw: unknown): string[] {
	if (!Array.isArray(raw)) return [];
	return raw.map((value) => String(value));
}

function toObjectArray(raw: unknown): Record<string, unknown>[] {
	if (!Array.isArray(raw)) return [];
	return raw.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null);
}

export function deriveV3BookletStatus(
	document: Record<string, unknown>,
	fallback: BookletStatus = 'draft_needs_review'
): BookletStatus {
	if (isBookletStatus(document.status)) return document.status;
	const sections = document.sections;
	if (Array.isArray(sections) && sections.length > 0) return fallback;
	return 'failed_unusable';
}

export function coerceV3DocumentToPack(
	generationId: string,
	document: Record<string, unknown>,
	options?: { templateId?: string; fallbackStatus?: BookletStatus }
): V3DraftPack | null {
	const rawSections = document.sections;
	if (!Array.isArray(rawSections) || rawSections.length === 0) return null;
	const sections = toObjectArray(rawSections);
	if (sections.length === 0) return null;

	const templateId =
		typeof document.template_id === 'string' && document.template_id
			? document.template_id
			: (options?.templateId ?? 'guided-concept-path');

	const sectionDiagnostics = toObjectArray(document.section_diagnostics).map((item) => {
		const status =
			item.status === 'complete' || item.status === 'incomplete' || item.status === 'failed'
				? item.status
				: 'incomplete';
		return {
			section_id: typeof item.section_id === 'string' ? item.section_id : '',
			status: status as 'complete' | 'incomplete' | 'failed',
			renderable: Boolean(item.renderable),
			missing_components: toStringArray(item.missing_components),
			missing_visuals: toStringArray(item.missing_visuals),
			warnings: toStringArray(item.warnings)
		};
	});

	const answerKey =
		typeof document.answer_key === 'object' && document.answer_key !== null
			? (document.answer_key as Record<string, unknown>)
			: null;

	return {
		generation_id:
			typeof document.generation_id === 'string' && document.generation_id
				? document.generation_id
				: generationId,
		blueprint_id:
			typeof document.blueprint_id === 'string' && document.blueprint_id
				? document.blueprint_id
				: '',
		template_id: templateId,
		subject: typeof document.subject === 'string' ? document.subject : '',
		status: deriveV3BookletStatus(document, options?.fallbackStatus),
		sections,
		answer_key: answerKey,
		warnings: toStringArray(document.warnings),
		section_diagnostics: sectionDiagnostics,
		booklet_issues: toObjectArray(document.booklet_issues)
	};
}
