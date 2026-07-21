import type { SectionContent } from 'lectio';
import type { GenerationDocument } from '$lib/types';
import { normalizeDocument } from '$lib/generation/viewer-state';

export type V3PackDocument = {
	generation_id?: string;
	blueprint_id?: string;
	template_id?: string;
	subject?: string;
	status?: string;
	sections?: Record<string, unknown>[];
	answer_key?: unknown;
	warnings?: string[];
	section_diagnostics?: unknown[];
	booklet_issues?: unknown[];
	visual_blocks?: Array<{
		visual_id: string;
		attaches_to: string;
		frame_index?: number | null;
		mode: 'diagram' | 'diagram_series' | 'diagram_compare' | 'image' | 'simulation';
		image_url?: string | null;
		status?: 'ready' | 'failed' | 'omitted_quality' | 'flagged_quality';
		qc_reasons?: string[];
		qc_correction_hint?: string | null;
	}>;
	progress?: {
		stage?: unknown;
		sections?: Record<string, string>;
		updated_at?: string;
	};
};

export type AdaptV3PackOptions = {
	/** When the pack omits `generation_id`, use the route param so consumers stay stable. */
	routeGenerationId?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function safeText(value: unknown): string {
	return typeof value === 'string' ? value.trim() : '';
}

function titleFromSectionId(sectionId: string): string {
	return sectionId
		.replaceAll('_', ' ')
		.replaceAll('-', ' ')
		.replace(/\b\w/g, (char) => char.toUpperCase());
}

function normalizeGradeBand(value: unknown): 'primary' | 'secondary' | 'advanced' {
	const text = safeText(value);
	if (text === 'primary' || text === 'secondary' || text === 'advanced') return text;
	return 'secondary';
}

/**
 * Map V3 booklet status strings onto legacy `GenerationDocument.status`.
 * Unknown values default to `partial` so draft/streaming packs stay printable.
 */
function mapPackStatus(status: string | undefined): GenerationDocument['status'] {
	if (status === 'failed_unusable') return 'failed';
	if (
		status === 'draft_ready' ||
		status === 'draft_with_warnings' ||
		status === 'draft_needs_review' ||
		status === 'streaming_preview'
	) {
		return 'partial';
	}
	if (status === 'final_ready' || status === 'final_with_warnings') {
		return 'completed';
	}
	if (status === 'pending' || status === 'running') {
		return status;
	}
	return 'partial';
}

function normalizeSection(
	raw: Record<string, unknown>,
	index: number,
	pack: V3PackDocument
): SectionContent {
	const sectionId = safeText(raw.section_id) || `section-${index + 1}`;
	const templateId =
		safeText(raw.template_id) || safeText(pack.template_id) || 'guided-concept-path';

	const rawHeader = isRecord(raw.header) ? raw.header : {};
	const title = safeText(rawHeader.title) || titleFromSectionId(sectionId);
	const subject = safeText(rawHeader.subject) || safeText(pack.subject) || 'Lesson';

	return {
		...raw,
		section_id: sectionId,
		template_id: templateId,
		header: {
			...rawHeader,
			title,
			subject,
			grade_band: normalizeGradeBand(rawHeader.grade_band)
		}
	} as SectionContent;
}

function buildGenerationDocument(
	pack: V3PackDocument,
	sections: SectionContent[],
	options: AdaptV3PackOptions
): GenerationDocument {
	const now = new Date().toISOString();
	const subject =
		safeText(pack.subject) || (sections[0]?.header && safeText(sections[0].header.subject)) || 'Lesson';
	const templateId = safeText(pack.template_id) || 'guided-concept-path';
	const generationId =
		safeText(pack.generation_id) || safeText(options.routeGenerationId) || '';

	const doc: GenerationDocument = {
		generation_id: generationId,
		subject,
		context: subject,
		mode: 'balanced',
		template_id: templateId,
		preset_id: 'blue-classroom',
		status: mapPackStatus(safeText(pack.status)),
		section_manifest: sections.map((section, index) => ({
			section_id: section.section_id,
			title: section.header?.title ?? titleFromSectionId(section.section_id),
			position: index + 1
		})),
		sections,
		partial_sections: [],
		failed_sections: [],
		qc_reports: [],
		quality_passed: null,
		error: null,
		created_at: now,
		updated_at: now,
		completed_at: now
	};

	return normalizeDocument(doc);
}

export function adaptV3PackToLectioDocument(
	pack: V3PackDocument,
	options: AdaptV3PackOptions = {}
): GenerationDocument {
	const rawSections = Array.isArray(pack.sections) ? pack.sections.filter(isRecord) : [];
	const sections = rawSections.map((section, index) => normalizeSection(section, index, pack));
	return buildGenerationDocument(pack, sections, options);
}

export type V3PackAdapterDiagnostic = {
	section_count: number;
	normalized_header_count: number;
	missing_section_ids: number;
	fields_by_section: Array<{ section_id: string; fields: string[] }>;
};

function buildAdapterDiagnostic(
	rawSections: Record<string, unknown>[],
	normalizedSections: SectionContent[]
): V3PackAdapterDiagnostic {
	let missing_section_ids = 0;
	let normalized_header_count = 0;
	for (const raw of rawSections) {
		if (!safeText(raw.section_id)) missing_section_ids += 1;
		const rh = isRecord(raw.header) ? raw.header : {};
		if (!safeText(rh.title)) normalized_header_count += 1;
	}
	const fields_by_section = rawSections.map((raw, index) => ({
		section_id: normalizedSections[index]?.section_id ?? `section-${index + 1}`,
		fields: Object.keys(raw)
	}));
	return {
		section_count: rawSections.length,
		normalized_header_count,
		missing_section_ids,
		fields_by_section
	};
}

export function adaptV3PackToLectioDocumentWithDiagnostics(
	pack: V3PackDocument,
	options: AdaptV3PackOptions = {}
): { document: GenerationDocument; diagnostic: V3PackAdapterDiagnostic } {
	const rawSections = Array.isArray(pack.sections) ? pack.sections.filter(isRecord) : [];
	const sections = rawSections.map((section, index) => normalizeSection(section, index, pack));
	return {
		document: buildGenerationDocument(pack, sections, options),
		diagnostic: buildAdapterDiagnostic(rawSections, sections)
	};
}
