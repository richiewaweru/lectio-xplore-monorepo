import { ensureOk } from '$lib/api/errors';
import { apiFetch } from '$lib/api/client';

/** Client-side print / PDF via browser print dialog (Save as PDF). */
export function printDocument(): void {
	if (typeof window !== 'undefined') {
		window.print();
	}
}

export type BuilderPdfAudience = 'teacher' | 'student';

export type BuilderPrintPreflightResult = {
	page_count_estimate: number;
	oversized_blocks: Array<Record<string, unknown>>;
	images: {
		loaded: number;
		failed: number;
		timed_out: number;
	};
	print_contract_coverage: Record<string, unknown>;
	warnings: string[];
};

export async function checkBuilderLessonPrint(
	lessonId: string,
	audience: BuilderPdfAudience = 'teacher'
): Promise<BuilderPrintPreflightResult> {
	const response = await apiFetch(`/api/v1/builder/lessons/${encodeURIComponent(lessonId)}/print-preflight`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ audience })
	});
	await ensureOk(response, 'Failed to check print layout.');
	return (await response.json()) as BuilderPrintPreflightResult;
}

export async function downloadBuilderLessonPdf(
	lessonId: string,
	audience: BuilderPdfAudience
): Promise<{ filename: string | null; pageCount: string | null }> {
	const response = await apiFetch(`/api/v1/builder/lessons/${encodeURIComponent(lessonId)}/export/pdf`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ audience })
	});
	await ensureOk(response, 'Failed to export lesson PDF.');

	const blob = await response.blob();
	const downloadUrl = URL.createObjectURL(blob);
	const anchor = document.createElement('a');
	const filename = parseFilename(response.headers.get('content-disposition'));
	anchor.href = downloadUrl;
	anchor.download = filename ?? `${lessonId}-${audience}.pdf`;
	anchor.click();
	URL.revokeObjectURL(downloadUrl);

	return {
		filename,
		pageCount: response.headers.get('x-page-count')
	};
}

function parseFilename(header: string | null): string | null {
	if (!header) {
		return null;
	}
	const match = /filename="?([^";]+)"?/i.exec(header);
	return match?.[1] ?? null;
}
