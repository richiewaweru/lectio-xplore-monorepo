import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('builder generation chrome print isolation', () => {
	it('keeps progress and issue text behind the print-hidden class', () => {
		const canvas = readFileSync(
			join(process.cwd(), 'src/lib/builder/components/canvas/BlockCanvas.svelte'),
			'utf8'
		);
		const printCss = readFileSync(join(process.cwd(), 'src/app.css'), 'utf8');

		expect(canvas).toMatch(/builder-print-hidden[^>]*data-unresolved-issue/);
		expect(canvas).toMatch(/builder-print-hidden[^>]*pending-section/);
		expect(printCss).toMatch(/\.builder-print-hidden[\s\S]*display:\s*none\s*!important/);
	});
});
