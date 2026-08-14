import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = process.cwd();
const layout = readFileSync(join(root, 'src/routes/+layout.svelte'), 'utf8');
const lessons = readFileSync(join(root, 'src/routes/lessons/+page.svelte'), 'utf8');
const settings = readFileSync(join(root, 'src/routes/settings/+page.svelte'), 'utf8');
const profileSummary = readFileSync(
	join(root, 'src/lib/components/workspace/ProfileSummary.svelte'),
	'utf8'
);

const paletteTokens = [
	'paper',
	'surface',
	'rule',
	'ink',
	'ink-2',
	'ink-3',
	'accent',
	'accent-soft',
	'amber',
	'amber-soft'
];

describe('workspace shell styling contract', () => {
	it('owns the workspace palette and font loading in the root layout', () => {
		for (const token of paletteTokens) {
			expect(layout.match(new RegExp(`--${token}:`, 'g'))).toHaveLength(1);
			expect(lessons).not.toContain(`--${token}:`);
		}
		expect(layout).toContain('font-family: Inter, sans-serif');
		expect(layout).toContain('family=Fraunces');
		expect(layout).toContain('family=IBM+Plex+Mono');
		expect(layout).toContain('family=Inter');
	});

	it('removes route-specific body styling and the legacy shell presentation', () => {
		expect(lessons).not.toContain('body:has(.workspace-page)');
		expect(layout).not.toContain('Iowan Old Style');
		expect(layout).not.toContain('radial-gradient');
		expect(layout).not.toContain('linear-gradient');
		expect(layout).not.toContain('workspace-kbd');
		expect(layout).not.toContain('⌘K');
	});

	it('keeps the complete Settings surface on shared tokens', () => {
		const literalColor = /#[0-9a-f]{3,8}\b|rgba?\(/i;
		expect(settings).not.toMatch(literalColor);
		expect(profileSummary).not.toMatch(literalColor);
		expect(settings).toContain('href="/units"');
	});

	it('preserves both print-shell exclusions', () => {
		expect(layout).toContain("page.url.pathname.startsWith('/studio/print/')");
		expect(layout).toContain("page.url.pathname.startsWith('/builder/print/')");
		expect(layout).toContain('isStudioPrintRoute || isBuilderPrintRoute');
	});
});
