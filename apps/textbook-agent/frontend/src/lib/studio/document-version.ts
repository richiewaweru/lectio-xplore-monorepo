import type { LectioDocument } from '@lectio/page';

/** Discriminate generation document payloads for v1 vs v2 renderers. */
export function extractLectioDocumentV2(payload: unknown): LectioDocument | null {
	if (!payload || typeof payload !== 'object') return null;
	const root = payload as Record<string, unknown>;
	const nested =
		root.lectio_document && typeof root.lectio_document === 'object'
			? (root.lectio_document as Record<string, unknown>)
			: null;
	const candidate =
		nested && nested.document_version === 2
			? nested
			: root.document_version === 2
				? root
				: null;
	if (!candidate) return null;
	if (typeof candidate.id !== 'string' || typeof candidate.title !== 'string') return null;
	if (!Array.isArray(candidate.sections)) return null;
	return candidate as unknown as LectioDocument;
}

export function documentRenderVersion(payload: unknown): 1 | 2 {
	return extractLectioDocumentV2(payload) ? 2 : 1;
}
