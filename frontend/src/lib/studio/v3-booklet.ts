import type { BookletStatus, V3DraftPack } from '$lib/types/v3';

export type BookletExportPolicy = {
	enabled: boolean;
	label: string;
	requiresConfirm: boolean;
};

export type BookletPrintReadiness = {
	label: string;
	detail: string;
	imageState: 'complete' | 'incomplete' | 'unavailable';
	missingVisualCount: number;
};

export function isBookletStatus(value: unknown): value is BookletStatus {
	return (
		value === 'streaming_preview' ||
		value === 'draft_ready' ||
		value === 'draft_with_warnings' ||
		value === 'draft_needs_review' ||
		value === 'final_ready' ||
		value === 'final_with_warnings' ||
		value === 'failed_unusable'
	);
}

export function getBookletStatusSummary(status: BookletStatus): string {
	switch (status) {
		case 'streaming_preview':
			return 'Writing lesson pieces...';
		case 'draft_ready':
			return 'Draft booklet ready - checking consistency.';
		case 'draft_with_warnings':
			return 'Draft booklet available with warnings.';
		case 'draft_needs_review':
			return 'Draft needs review before classroom use.';
		case 'final_ready':
			return 'Final booklet ready.';
		case 'final_with_warnings':
			return 'Final booklet ready with minor warnings.';
		default:
			return 'No usable booklet could be assembled.';
	}
}

export function getBookletExportPolicy(status: BookletStatus): BookletExportPolicy {
	switch (status) {
		case 'final_ready':
			return { enabled: true, label: 'Download Final PDF', requiresConfirm: false };
		case 'final_with_warnings':
			return { enabled: true, label: 'Download Final PDF (Warnings)', requiresConfirm: false };
		case 'draft_ready':
			return { enabled: true, label: 'Download Draft PDF', requiresConfirm: false };
		case 'draft_with_warnings':
			return { enabled: true, label: 'Download Draft PDF (Warnings)', requiresConfirm: false };
		case 'draft_needs_review':
			return { enabled: true, label: 'Download Draft PDF (Review Needed)', requiresConfirm: false };
		default:
			return { enabled: false, label: 'Export Unavailable', requiresConfirm: false };
	}
}

export function countMissingVisuals(
	pack: Pick<V3DraftPack, 'section_diagnostics'> | null | undefined
): number {
	if (!pack) return 0;
	return pack.section_diagnostics.reduce(
		(total, diagnostic) => total + diagnostic.missing_visuals.length,
		0
	);
}

export function getBookletPrintReadiness(
	status: BookletStatus,
	pack: Pick<V3DraftPack, 'section_diagnostics'> | null | undefined
): BookletPrintReadiness {
	const policy = getBookletExportPolicy(status);
	const missingVisualCount = countMissingVisuals(pack);
	if (!policy.enabled) {
		return {
			label: 'Print unavailable',
			detail: 'A printable booklet is not available yet.',
			imageState: 'unavailable',
			missingVisualCount
		};
	}
	if (missingVisualCount > 0) {
		return {
			label: 'Text ready - images not complete (text-only print)',
			detail: `Text sections are printable now. ${missingVisualCount} visual slot${missingVisualCount === 1 ? ' is' : 's are'} still pending or failed.`,
			imageState: 'incomplete',
			missingVisualCount
		};
	}
	return {
		label: 'Ready to print',
		detail: 'Text and images are complete for print output.',
		imageState: 'complete',
		missingVisualCount
	};
}
