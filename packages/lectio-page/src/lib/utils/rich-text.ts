import type { InlineNode, RichText } from '../contract/document';

/** Visible plain text from rich text / inline nodes (ignores JSON keys). */
export function visibleText(value: RichText | string | null | undefined): string {
	if (value == null) return '';
	if (typeof value === 'string') return value;
	return value.map(inlineVisible).join('');
}

function inlineVisible(node: InlineNode): string {
	switch (node.type) {
		case 'text':
		case 'term':
			return node.value;
		case 'math':
			return node.latex;
		case 'reference':
			return node.label;
		case 'strong':
		case 'emphasis':
		case 'small-caps':
			return node.children.map(inlineVisible).join('');
		default:
			return '';
	}
}

export function wordCount(value: RichText | string | null | undefined): number {
	return visibleText(value)
		.split(/\s+/)
		.filter(Boolean).length;
}
