import type { InlineNode, RichText } from '../contract/document';

export function asRichText(value: RichText | string | null | undefined): InlineNode[] {
	if (value == null) return [];
	if (typeof value === 'string') return [{ type: 'text', value }];
	return value;
}

export function plainText(value: RichText | string | null | undefined): string {
	return asRichText(value)
		.map((node) => {
			if (node.type === 'text' || node.type === 'term') return node.value;
			if (node.type === 'math') return node.latex;
			if (node.type === 'reference') return node.label;
			if ('children' in node) return plainText(node.children);
			return '';
		})
		.join('');
}
