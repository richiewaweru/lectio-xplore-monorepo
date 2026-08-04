import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const LECTIO_ENTRY = require.resolve('lectio');
const LECTIO_ROOT = resolve(dirname(LECTIO_ENTRY), '..');
const DIAGRAM_LED_LAYOUT = resolve(LECTIO_ROOT, 'dist/templates/diagram-led/layout.svelte');

describe('diagram-led package layout source', () => {
	it('renders the expected core diagram-led components from the published Lectio package', () => {
		const source = readFileSync(DIAGRAM_LED_LAYOUT, 'utf8');

		expect(source).toContain('HookHero');
		expect(source).toContain('DiagramSeries');
		expect(source).toContain('{#if section.diagram_series}');
		expect(source).toContain('<DiagramSeries content={section.diagram_series} />');
		expect(source).toContain('<PracticeStack content={section.practice} mode="accordion" />');
	});
});
