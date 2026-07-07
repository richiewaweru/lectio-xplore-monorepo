import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC_ROOT = resolve(HERE, '..');

const IMPORT_PATTERNS = [
	/\bfrom\s+['"][^'"]*vendor\/lectio[^'"]*['"]/,
	/\bimport\s*\(\s*['"][^'"]*vendor\/lectio[^'"]*['"]\s*\)/,
	/\brequire\s*\(\s*['"][^'"]*vendor\/lectio[^'"]*['"]\s*\)/
];

function walkFiles(root: string): string[] {
	const entries = readdirSync(root);
	const files: string[] = [];

	for (const entry of entries) {
		const fullPath = resolve(root, entry);
		const stats = statSync(fullPath);
		if (stats.isDirectory()) {
			files.push(...walkFiles(fullPath));
			continue;
		}
		if (!fullPath.endsWith('.ts') && !fullPath.endsWith('.svelte')) {
			continue;
		}
		files.push(fullPath);
	}

	return files;
}

describe('frontend vendor import guard', () => {
	it('does not import vendored lectio paths from frontend source or tests', () => {
		const violations: string[] = [];

		for (const filePath of walkFiles(SRC_ROOT)) {
			const source = readFileSync(filePath, 'utf8');
			if (IMPORT_PATTERNS.some((pattern) => pattern.test(source))) {
				violations.push(filePath);
			}
		}

		expect(violations).toEqual([]);
	}, 30_000);
});
