import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
const APP_CSS_PATH = resolve(HERE, '..', 'app.css');

describe('lectio theme import guard', () => {
	it('keeps lectio/theme.css imported in app.css', () => {
		const css = readFileSync(APP_CSS_PATH, 'utf8');
		expect(css).toMatch(/@import\s+['"]lectio\/theme\.css['"];/);
	});
});
