import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const read = (p: string) => readFileSync(join(root, p), 'utf8');

describe('base-print.css export parity', () => {
	it('keeps all three copies byte-identical', () => {
		const source = read('src/lib/print/base-print.css');
		expect(read('contracts/base-print.css')).toBe(source);
		expect(read('docs/architecture/page-objects/contracts/base-print.css')).toBe(source);
	});

	it('declares exactly one @page rule', () => {
		const matches = read('src/lib/print/base-print.css').match(/@page\b/g) ?? [];
		expect(matches).toHaveLength(1);
	});
});
