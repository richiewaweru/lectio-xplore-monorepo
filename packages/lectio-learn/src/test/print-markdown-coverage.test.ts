import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { PRINT_MARKDOWN_REQUIREMENTS } from '$lib/print/markdown-requirements';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(HERE, '..', '..');

describe('print utility markdown coverage', () => {
	for (const [filePath, requirements] of Object.entries(PRINT_MARKDOWN_REQUIREMENTS)) {
		it(`${filePath} applies markdown to all required fields`, () => {
			const source = readFileSync(resolve(PROJECT_ROOT, filePath), 'utf8');

			for (const { field, renderer } of requirements) {
				expect(source, `${filePath} must render ${field} with ${renderer}`).toContain(renderer);
			}
		});
	}
});
