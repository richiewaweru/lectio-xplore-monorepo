import type { InlineNode, RichText } from '../contract/document';

type MarkupFrame = 'strong' | 'emphasis' | 'small-caps';

const LEGACY_MARKUP_TAG = /<\/?(strong|b|em|i|small-caps|smallcaps)\s*>/gi;
const LEGACY_MARKUP_TAG_PATTERN = /<\/?(strong|b|em|i|small-caps|smallcaps)\s*>|(?:\*\*|__)[^\n]+?(?:\*\*|__)/i;

function appendText(nodes: InlineNode[], value: string): void {
  if (!value) return;
  const previous = nodes[nodes.length - 1];
  if (previous?.type === 'text') previous.value += value;
  else nodes.push({ type: 'text', value });
}

function closeFrame(
  stack: Array<{ type: MarkupFrame; children: InlineNode[] }>,
  type: MarkupFrame,
  root: InlineNode[]
): void {
  const index = stack.map((frame) => frame.type).lastIndexOf(type);
  if (index < 0) return;
  const frame = stack.splice(index, 1)[0];
  const parent = stack[stack.length - 1]?.children;
  (parent ?? root).push({ type: frame.type, children: frame.children });
}

/**
 * Convert the small legacy HTML emphasis subset found in older generated
 * prose into the typed inline contract. Raw HTML is intentionally never
 * passed through to the renderer.
 */
function legacyMarkupToRichText(value: string): InlineNode[] {
  const normalized = value
    .replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>')
    .replace(/__(.+?)__/gs, '<strong>$1</strong>');
  const root: InlineNode[] = [];
  const stack: Array<{ type: MarkupFrame; children: InlineNode[] }> = [];
  let cursor = 0;
  for (const match of normalized.matchAll(LEGACY_MARKUP_TAG)) {
    const text = normalized.slice(cursor, match.index ?? cursor);
    appendText(stack[stack.length - 1]?.children ?? root, text);
    const tag = (match[1] ?? '').toLowerCase();
    const type: MarkupFrame = tag === 'strong' || tag === 'b'
      ? 'strong'
      : tag === 'em' || tag === 'i'
        ? 'emphasis'
        : 'small-caps';
    if (match[0].startsWith('</')) closeFrame(stack, type, root);
    else stack.push({ type, children: [] });
    cursor = (match.index ?? cursor) + match[0].length;
  }
  appendText(stack[stack.length - 1]?.children ?? root, normalized.slice(cursor));
  while (stack.length) closeFrame(stack, stack[stack.length - 1].type, root);
  return root;
}

export function asRichText(value: RichText | string | null | undefined): InlineNode[] {
	if (value == null) return [];
	if (typeof value === 'string') {
    return LEGACY_MARKUP_TAG_PATTERN.test(value)
      ? legacyMarkupToRichText(value)
      : [{ type: 'text', value }];
	}
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
