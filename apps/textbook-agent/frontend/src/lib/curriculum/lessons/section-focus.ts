/**
 * Shared "Go to section" behaviour for the Learn builder and the Print editor.
 *
 * The Issues tab links to `<editor>?section=<section_id>`; the editor finds the
 * rendered section (`data-section-id`, falling back to the Print renderer's
 * `id`), scrolls it into view and highlights it briefly.
 */

export const SECTION_QUERY_PARAM = 'section';
export const SECTION_HIGHLIGHT_CLASS = 'lectio-section-focus';
const STYLE_ELEMENT_ID = 'lectio-section-focus-style';
const HIGHLIGHT_MS = 2600;

/** `/builder/<id>` or `/studio/print/<id>` with the section to open; `null` when there is nothing to link to. */
export function sectionHref(editBaseHref: string | null | undefined, sectionId: string | null | undefined): string | null {
	if (!editBaseHref || !sectionId) return null;
	return `${editBaseHref}?${SECTION_QUERY_PARAM}=${encodeURIComponent(sectionId)}`;
}

export function findSectionElement(sectionId: string, root: ParentNode = document): HTMLElement | null {
	const escaped = sectionId.replace(/["\\]/g, '\\$&');
	const tagged = root.querySelector<HTMLElement>(`[data-section-id="${escaped}"]`);
	if (tagged) return tagged;
	// The Print renderer already gives each section its own id.
	const byId = root.querySelector<HTMLElement>(`.lectio-section[id="${escaped}"]`);
	return byId;
}

function ensureHighlightStyle(): void {
	if (typeof document === 'undefined' || document.getElementById(STYLE_ELEMENT_ID)) return;
	const style = document.createElement('style');
	style.id = STYLE_ELEMENT_ID;
	style.textContent = `.${SECTION_HIGHLIGHT_CLASS}{outline:3px solid #f59e0b;outline-offset:4px;background:rgba(245,158,11,.12);border-radius:6px;transition:background .4s ease,outline-color .4s ease}`;
	document.head.appendChild(style);
}

/** Scroll the section into view and highlight it. Returns whether it was found. */
export function focusSection(sectionId: string | null | undefined, root: ParentNode = document): boolean {
	if (!sectionId) return false;
	const element = findSectionElement(sectionId, root);
	if (!element) return false;
	ensureHighlightStyle();
	element.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
	element.classList.add(SECTION_HIGHLIGHT_CLASS);
	setTimeout(() => element.classList.remove(SECTION_HIGHLIGHT_CLASS), HIGHLIGHT_MS);
	return true;
}

/** The editors render asynchronously, so retry briefly until the section exists. */
export async function focusSectionWhenReady(
	sectionId: string | null | undefined,
	options: { attempts?: number; intervalMs?: number; root?: ParentNode } = {}
): Promise<boolean> {
	const { attempts = 20, intervalMs = 100, root } = options;
	for (let attempt = 0; attempt < attempts; attempt += 1) {
		if (focusSection(sectionId, root)) return true;
		await new Promise((resolve) => setTimeout(resolve, intervalMs));
	}
	return false;
}
