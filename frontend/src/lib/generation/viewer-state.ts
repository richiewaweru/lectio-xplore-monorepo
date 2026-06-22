import type { SectionContent } from 'lectio';

import { parseIncomingSection } from '$lib/parse-section';
import type {
	FailedSectionEntry,
	GenerationDocument,
	PipelinePartialSectionEntry,
	PipelineSectionManifestItem,
	SectionAssetPendingEvent,
	SectionAssetReadyEvent,
	SectionFailedEvent,
	SectionFinalEvent,
	SectionPartialEvent,
	SectionReadyEvent,
	SectionStartedEvent
} from '$lib/types';

export interface ViewerWarning {
	message: string;
}

export type ViewerSectionStatus =
	| 'planned'
	| 'generating'
	| 'partially_ready'
	| 'blocked_by_required_media'
	| 'ready'
	| 'failed'
	| 'unplanned_output';

export interface ViewerSectionSignal {
	status: ViewerSectionStatus;
	reason?: string | null;
	slot_ids?: string[];
	label?: string | null;
}

export interface ViewerSectionSlot {
	section_id: string;
	title: string;
	position: number;
	status: ViewerSectionStatus;
	section: SectionContent | null;
	partial: PipelinePartialSectionEntry | null;
	failure: FailedSectionEntry | null;
	signal: ViewerSectionSignal | null;
}

function sortManifest(
	manifest: PipelineSectionManifestItem[] | undefined
): PipelineSectionManifestItem[] {
	const byId = new Map<string, PipelineSectionManifestItem>();
	for (const item of manifest ?? []) {
		byId.set(item.section_id, item);
	}
	return [...byId.values()].sort(
		(left, right) => left.position - right.position || left.section_id.localeCompare(right.section_id)
	);
}

function sortSectionsByManifest(
	sections: SectionContent[],
	manifest: PipelineSectionManifestItem[]
): SectionContent[] {
	if (manifest.length === 0) {
		return sections;
	}

	const positions = new Map(manifest.map((item) => [item.section_id, item.position]));
	const fallbackPosition = manifest.length + 1;
	return [...sections].sort((left, right) => {
		const leftPosition = positions.get(left.section_id) ?? fallbackPosition;
		const rightPosition = positions.get(right.section_id) ?? fallbackPosition;
		return leftPosition - rightPosition || left.section_id.localeCompare(right.section_id);
	});
}

function sortFailedSections(
	failedSections: FailedSectionEntry[],
	manifest: PipelineSectionManifestItem[]
): FailedSectionEntry[] {
	const positions = new Map(manifest.map((item) => [item.section_id, item.position]));
	const fallbackPosition = manifest.length + 1;
	return [...failedSections].sort((left, right) => {
		const leftPosition = positions.get(left.section_id) ?? left.position ?? fallbackPosition;
		const rightPosition = positions.get(right.section_id) ?? right.position ?? fallbackPosition;
		return leftPosition - rightPosition || left.section_id.localeCompare(right.section_id);
	});
}

function sortPartialSections(
	partialSections: PipelinePartialSectionEntry[],
	manifest: PipelineSectionManifestItem[]
): PipelinePartialSectionEntry[] {
	const positions = new Map(manifest.map((item) => [item.section_id, item.position]));
	const fallbackPosition = manifest.length + 1;
	return [...partialSections].sort((left, right) => {
		const leftPosition = positions.get(left.section_id) ?? fallbackPosition;
		const rightPosition = positions.get(right.section_id) ?? fallbackPosition;
		return leftPosition - rightPosition || left.section_id.localeCompare(right.section_id);
	});
}

function replaceOrAppendPartialSection(
	document: GenerationDocument,
	entry: PipelinePartialSectionEntry
): GenerationDocument {
	const partialSections = [...(document.partial_sections ?? [])];
	const existingIndex = partialSections.findIndex((item) => item.section_id === entry.section_id);
	if (existingIndex >= 0) {
		partialSections[existingIndex] = entry;
	} else {
		partialSections.push(entry);
	}

	return normalizeDocument({
		...document,
		status: 'running',
		updated_at: new Date().toISOString(),
		partial_sections: partialSections,
		failed_sections: document.failed_sections.filter((item) => item.section_id !== entry.section_id)
	});
}

function updatePartialSectionAssets(
	document: GenerationDocument,
	sectionId: string,
	partialStatus: string,
	pendingAssets: string[],
	visualMode: 'svg' | 'image' | null | undefined,
	updatedAt: string
): GenerationDocument {
	const partialSections = [...(document.partial_sections ?? [])];
	const existingIndex = partialSections.findIndex((item) => item.section_id === sectionId);
	if (existingIndex < 0) {
		return document;
	}

	partialSections[existingIndex] = {
		...partialSections[existingIndex],
		status: partialStatus,
		visual_mode: visualMode ?? partialSections[existingIndex].visual_mode ?? null,
		pending_assets: [...pendingAssets],
		updated_at: updatedAt
	};

	return normalizeDocument({
		...document,
		status: 'running',
		updated_at: new Date().toISOString(),
		partial_sections: partialSections
	});
}

function derivePartialSlotStatus(entry: PipelinePartialSectionEntry): ViewerSectionStatus {
	if (entry.pending_assets.length > 0 || entry.status === 'awaiting_assets') {
		return 'partially_ready';
	}
	return 'generating';
}

function normalizeFailedSectionEntry(entry: FailedSectionEntry): FailedSectionEntry {
	const visualPlacementsCount = entry.visual_placements_count ?? (entry.needs_diagram ? 1 : 0);
	return {
		...entry,
		visual_placements_count: visualPlacementsCount,
		needs_diagram: visualPlacementsCount > 0
	};
}

export function normalizeDocument(document: GenerationDocument): GenerationDocument {
	const section_manifest = sortManifest(document.section_manifest);
	return {
		...document,
		section_manifest,
		sections: sortSectionsByManifest(document.sections, section_manifest),
		partial_sections: sortPartialSections(document.partial_sections ?? [], section_manifest),
		failed_sections: sortFailedSections(
			(document.failed_sections ?? []).map(normalizeFailedSectionEntry),
			section_manifest
		)
	};
}

export function applySectionStarted(
	document: GenerationDocument,
	payload: SectionStartedEvent
): GenerationDocument {
	return normalizeDocument({
		...document,
		status: 'running',
		updated_at: new Date().toISOString(),
		section_manifest: [
			...document.section_manifest,
			{
				section_id: payload.section_id,
				title: payload.title,
				position: payload.position
			}
		]
	});
}

export function applySectionPartial(
	document: GenerationDocument,
	payload: SectionPartialEvent
): { document: GenerationDocument; warning: ViewerWarning | null } {
	try {
		const section = parseIncomingSection(payload.section);
		const entry: PipelinePartialSectionEntry = {
			section_id: payload.section_id,
			template_id: payload.template_id,
			content: section,
			status: payload.status,
			visual_mode: payload.visual_mode ?? null,
			pending_assets: [...payload.pending_assets],
			updated_at: payload.updated_at
		};

		return {
			document: replaceOrAppendPartialSection(document, entry),
			warning: null
		};
	} catch (error) {
		return {
			document,
			warning: {
				message:
					error instanceof Error ? error.message : '[Lectio] Invalid partial section from generation stream.'
			}
		};
	}
}

export function applySectionAssetPending(
	document: GenerationDocument,
	payload: SectionAssetPendingEvent
): GenerationDocument {
	return updatePartialSectionAssets(
		document,
		payload.section_id,
		payload.status,
		payload.pending_assets,
		payload.visual_mode,
		payload.updated_at
	);
}

export function applySectionAssetReady(
	document: GenerationDocument,
	payload: SectionAssetReadyEvent
): GenerationDocument {
	return updatePartialSectionAssets(
		document,
		payload.section_id,
		payload.pending_assets.length > 0 ? 'awaiting_assets' : 'finalizing',
		payload.pending_assets,
		payload.visual_mode,
		payload.updated_at
	);
}

export function applySectionFinal(
	document: GenerationDocument,
	payload: Pick<SectionFinalEvent, 'section_id'>
): GenerationDocument {
	return normalizeDocument({
		...document,
		status: 'running',
		updated_at: new Date().toISOString(),
		partial_sections: (document.partial_sections ?? []).map((entry) =>
			entry.section_id === payload.section_id
				? { ...entry, status: 'finalizing', pending_assets: [] }
				: entry
		)
	});
}

export function applySectionReady(
	document: GenerationDocument,
	payload: Pick<SectionReadyEvent, 'section' | 'section_id'>
): { document: GenerationDocument; warning: ViewerWarning | null } {
	try {
		const section = parseIncomingSection(payload.section);
		const sections = [...document.sections];
		const existingIndex = sections.findIndex((entry) => entry.section_id === section.section_id);
		if (existingIndex >= 0) {
			sections[existingIndex] = section;
		} else {
			sections.push(section);
		}

		return {
			document: normalizeDocument({
				...document,
				status: 'running',
				updated_at: new Date().toISOString(),
				sections,
				partial_sections: (document.partial_sections ?? []).filter(
					(entry) => entry.section_id !== payload.section_id
				),
				failed_sections: document.failed_sections.filter(
					(entry) => entry.section_id !== payload.section_id
				)
			}),
			warning: null
		};
	} catch (error) {
		return {
			document,
			warning: {
				message:
					error instanceof Error ? error.message : '[Lectio] Invalid section from generation stream.'
			}
		};
	}
}

export function applySectionFailed(
	document: GenerationDocument,
	payload: SectionFailedEvent
): GenerationDocument {
	const failedSections = [...document.failed_sections];
	const visualPlacementsCount = payload.visual_placements_count ?? (payload.needs_diagram ? 1 : 0);
	const nextFailed: FailedSectionEntry = {
		section_id: payload.section_id,
		title: payload.title,
		position: payload.position,
		focus: payload.focus ?? null,
		bridges_from: payload.bridges_from ?? null,
		bridges_to: payload.bridges_to ?? null,
		needs_diagram: visualPlacementsCount > 0,
		visual_placements_count: visualPlacementsCount,
		needs_worked_example: payload.needs_worked_example,
		failed_at_node: payload.failed_at_node,
		error_type: payload.error_type,
		error_summary: payload.error_summary,
		attempt_count: payload.attempt_count,
		can_retry: payload.can_retry,
		missing_components: payload.missing_components,
		failure_detail: payload.failure_detail ?? null
	};
	const existingIndex = failedSections.findIndex((entry) => entry.section_id === payload.section_id);
	if (existingIndex >= 0) {
		failedSections[existingIndex] = nextFailed;
	} else {
		failedSections.push(nextFailed);
	}

	return normalizeDocument({
		...document,
		status: document.status === 'failed' ? 'failed' : 'running',
		updated_at: new Date().toISOString(),
		failed_sections: failedSections,
		partial_sections: (document.partial_sections ?? []).filter(
			(entry) => entry.section_id !== payload.section_id
		),
		sections: document.sections.filter((entry) => entry.section_id !== payload.section_id)
	});
}

export function buildSectionSlots(
	document: GenerationDocument | null,
	sectionCount: number | null,
	sectionSignals: Record<string, ViewerSectionSignal> = {}
): ViewerSectionSlot[] {
	if (!document && !sectionCount) {
		return [];
	}

	const normalized = document ? normalizeDocument(document) : null;
	const manifest = normalized?.section_manifest ?? [];
	const readySections = normalized?.sections ?? [];
	const failedSections = normalized?.failed_sections ?? [];
	const partialSections = normalized?.partial_sections ?? [];
	const readyById = new Map(readySections.map((section) => [section.section_id, section]));
	const failedById = new Map(failedSections.map((section) => [section.section_id, section]));
	const partialById = new Map(partialSections.map((section) => [section.section_id, section]));
	const terminal = normalized
		? ['completed', 'partial', 'failed'].includes(normalized.status)
		: false;

	if (manifest.length > 0) {
		const manifestIds = new Set(manifest.map((item) => item.section_id));
		const slots = manifest.map((item) => {
			const ready = readyById.get(item.section_id) ?? null;
			const failed = failedById.get(item.section_id) ?? null;
			const partial = partialById.get(item.section_id) ?? null;
			const signal = sectionSignals[item.section_id] ?? null;
			const status: ViewerSectionStatus = ready
				? 'ready'
				: failed
					? 'failed'
					: signal
						? signal.status
						: partial
							? derivePartialSlotStatus(partial)
							: terminal
								? 'failed'
								: 'planned';

			return {
				section_id: item.section_id,
				title: item.title,
				position: item.position,
				status,
				section: ready,
				partial,
				failure: failed,
				signal
			};
		}) satisfies ViewerSectionSlot[];

		const orphanReady = readySections
			.filter((section) => !manifestIds.has(section.section_id))
			.map((section, index) => ({
				section_id: section.section_id,
				title: section.header?.title ?? section.section_id,
				position: manifest.length + index + 1,
				status: 'unplanned_output' as const,
				section,
				partial: null,
				failure: null,
				signal: sectionSignals[section.section_id] ?? null
			}));
		const orphanPartial = partialSections
			.filter((section) => !manifestIds.has(section.section_id))
			.map((section, index) => ({
				section_id: section.section_id,
				title: section.content.header?.title ?? section.section_id,
				position: manifest.length + orphanReady.length + index + 1,
				status: 'unplanned_output' as const,
				section: null,
				partial: section,
				failure: null,
				signal: sectionSignals[section.section_id] ?? null
			}));
		const orphanFailed = failedSections
			.filter((section) => !manifestIds.has(section.section_id))
			.map((section, index) => ({
				section_id: section.section_id,
				title: section.title,
				position: manifest.length + orphanReady.length + orphanPartial.length + index + 1,
				status: 'unplanned_output' as const,
				section: null,
				partial: null,
				failure: section,
				signal: sectionSignals[section.section_id] ?? null
			}));
		return [...slots, ...orphanReady, ...orphanPartial, ...orphanFailed];
	}

	const total = Math.max(
		sectionCount ?? 0,
		readySections.length,
		failedSections.length,
		partialSections.length
	);
	return Array.from({ length: total }, (_, index) => {
		const ready = readySections[index] ?? null;
		const failed = failedSections[index] ?? null;
		const partial = partialSections[index] ?? null;
		const signal = sectionSignals[
			ready?.section_id ?? failed?.section_id ?? partial?.section_id ?? `pending-${index + 1}`
		] ?? null;
		const status: ViewerSectionStatus = ready
			? 'ready'
			: failed
				? 'failed'
				: signal
					? signal.status
					: partial
						? derivePartialSlotStatus(partial)
						: terminal
							? 'failed'
							: 'planned';
		return {
			section_id: ready?.section_id ?? failed?.section_id ?? partial?.section_id ?? `pending-${index + 1}`,
			title:
				ready?.header?.title ??
				failed?.title ??
				partial?.content.header?.title ??
				`Section ${index + 1}`,
			position: index + 1,
			status,
			section: ready,
			partial,
			failure: failed,
			signal
		};
	});
}
