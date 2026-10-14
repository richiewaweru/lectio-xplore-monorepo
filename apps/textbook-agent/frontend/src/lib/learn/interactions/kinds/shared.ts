import type { ItemResults } from '../types';

/** Accepts a plain string (id = label) or an object {id, label?}. */
export function toChoice(v: unknown): { id: string; label: string } {
	if (typeof v === 'object' && v !== null) {
		const o = v as { id?: unknown; label?: unknown };
		return { id: String(o.id), label: String(o.label ?? o.id) };
	}
	return { id: String(v), label: String(v) };
}

export function sequenceItems(cfg: Record<string, unknown>): Array<{ id: string; label: string }> {
	if (Array.isArray(cfg.items)) return (cfg.items as unknown[]).map(toChoice);
	if (Array.isArray(cfg.order)) {
		return cfg.order.map((id) => ({ id: String(id), label: String(id) }));
	}
	return [];
}

export function choiceOptions(
	cfg: Record<string, unknown>
): Array<{ id: string; text: string; letter: string }> {
	return Array.isArray(cfg.options)
		? (cfg.options as Array<{ id: string; text?: string; label?: string }>).map((o, index) => ({
				id: String(o.id),
				text: String(o.text ?? o.label ?? o.id),
				letter: String.fromCharCode(65 + index)
			}))
		: [];
}

/** {id: bool} item results (choice, multi-select, match, classify). */
export function mapResults(r: ItemResults | undefined): Record<string, boolean> | null {
	return r && !Array.isArray(r) ? r : null;
}

/** bool[] item results (sequence, fill-blank). */
export function listResults(r: ItemResults | undefined): boolean[] | null {
	return Array.isArray(r) ? r : null;
}
