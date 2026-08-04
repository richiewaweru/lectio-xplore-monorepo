import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { validateDocument, PAGE_OBJECTS, INTENT_IDS } from '$lib/contract';
import { listIntents, listObjects, isCompatible } from '$lib/catalogue';

const root = join(process.cwd());

describe('v2 contracts', () => {
	it('exposes ten objects and thirty-two intents', () => {
		expect(PAGE_OBJECTS).toHaveLength(10);
		expect(INTENT_IDS).toHaveLength(32);
		expect(listObjects()).toHaveLength(10);
		expect(listIntents()).toHaveLength(32);
	});

	it('validates the empty fixture', () => {
		const doc = JSON.parse(readFileSync(join(root, 'fixtures/empty-document.json'), 'utf8'));
		expect(validateDocument(doc)).toEqual([]);
	});

	it('validates the photosynthesis fixture', () => {
		const doc = JSON.parse(readFileSync(join(root, 'fixtures/photosynthesis-ref.json'), 'utf8'));
		const issues = validateDocument(doc);
		expect(issues).toEqual([]);
	});

	it('treats heading as structural (no intent compatibility)', () => {
		expect(isCompatible('heading', 'orient')).toBe(false);
		expect(isCompatible('aside', 'warn')).toBe(true);
		expect(isCompatible('prose', 'answer-key')).toBe(false);
	});
});
