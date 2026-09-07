// @vitest-environment node

import { describe, expect, it } from 'vitest';

import { renderBlockMarkdown, renderInlineMarkdown } from './markdown';
import { sanitizeSvg } from './sanitize';

describe('markdown SSR rendering', () => {
	it('renders and sanitizes markdown without a browser window', () => {
		const rendered = renderInlineMarkdown('A **strong** idea');

		expect(rendered).toContain('<strong>strong</strong>');
		expect(rendered).not.toContain('<script');
	});

	it('sanitizes direct HTML on the server path', () => {
		const rendered = renderBlockMarkdown(
			'<p>Safe copy</p><script>globalThis.compromised = true</script>'
		);

		expect(rendered).toContain('<p>Safe copy</p>');
		expect(rendered).not.toContain('<script');
		expect(rendered).not.toContain('compromised');
	});

	it('sanitizes SVG without a browser window', () => {
		const rendered = sanitizeSvg(
			'<svg><circle cx="10" cy="10" r="5" /><script>globalThis.compromised = true</script></svg>'
		);

		expect(rendered).toContain('<circle');
		expect(rendered).not.toContain('<script');
		expect(rendered).not.toContain('compromised');
	});
});
