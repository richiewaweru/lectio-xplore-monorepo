import DOMPurify from 'isomorphic-dompurify';
import katex from 'katex';
import { marked } from 'marked';

const INLINE_MATH_REGEX = /(?<!\\|\$)\$([^\n$]+?)\$(?!\$)/g;
const DISPLAY_MATH_REGEX = /\$\$([\s\S]+?)\$\$/g;
const HTML_TAG_PATTERN = /<[a-z][\s\S]*>/i;

const KATEX_SVG_TAGS = [
	'svg',
	'g',
	'path',
	'line',
	'rect',
	'circle',
	'ellipse',
	'polygon',
	'polyline',
	'defs',
	'use',
	'marker',
	'title',
	'desc',
	'clipPath'
];

const KATEX_ATTRS = [
	'xmlns',
	'width',
	'height',
	'viewBox',
	'x',
	'y',
	'x1',
	'x2',
	'y1',
	'y2',
	'd',
	'transform',
	'fill',
	'fill-rule',
	'stroke',
	'stroke-width',
	'stroke-linecap',
	'stroke-linejoin',
	'stroke-dasharray',
	'stroke-dashoffset',
	'opacity',
	'points',
	'r',
	'rx',
	'ry',
	'cx',
	'cy',
	'preserveAspectRatio',
	'focusable',
	'aria-hidden',
	'role',
	'class',
	'style'
];

function escapeHtml(text: string): string {
	return text
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

function renderMath(expr: string, displayMode: boolean): string {
	try {
		return katex.renderToString(expr.trim(), {
			displayMode,
			throwOnError: true,
			trust: false
		});
	} catch {
		const escaped = escapeHtml(expr.trim());
		return displayMode
			? `<div class="math-error">$$${escaped}$$</div>`
			: `<span class="math-error">$${escaped}$</span>`;
	}
}

function preprocessMath(text: string): string {
	return text
		.replace(DISPLAY_MATH_REGEX, (_match, expr: string) => renderMath(expr, true))
		.replace(INLINE_MATH_REGEX, (_match, expr: string) => renderMath(expr, false));
}

function sanitizeHtml(html: string): string {
	return DOMPurify.sanitize(html, {
		USE_PROFILES: { html: true, svg: true, svgFilters: true },
		ADD_TAGS: KATEX_SVG_TAGS,
		ADD_ATTR: KATEX_ATTRS,
		ALLOW_DATA_ATTR: false
	});
}

export function renderInlineMarkdown(text: string): string {
	if (!text) return '';
	if (HTML_TAG_PATTERN.test(text)) return sanitizeHtml(text);
	const parsed = marked.parseInline(preprocessMath(text), { gfm: true });
	return sanitizeHtml(typeof parsed === 'string' ? parsed : '');
}

export function renderBlockMarkdown(text: string): string {
	if (!text) return '';
	if (HTML_TAG_PATTERN.test(text)) return sanitizeHtml(text);
	const parsed = marked.parse(preprocessMath(text), { gfm: true, breaks: true });
	return sanitizeHtml(typeof parsed === 'string' ? parsed : '');
}

/**
 * Returns true if the string contains LaTeX control sequences.
 * Used to decide whether to send notation through KaTeX or render as prose.
 */
export function looksLikeLatex(text: string): boolean {
  return /[\\^_{}\[\]]|\\[a-zA-Z]/.test(text);
}
