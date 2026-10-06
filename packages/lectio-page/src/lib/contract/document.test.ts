import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { validateDocument, PAGE_OBJECTS, INTENT_IDS } from '$lib/contract';
import { listIntents, listObjects, isCompatible } from '$lib/catalogue';

const root = join(process.cwd());

describe('v2 contracts', () => {
	it('exposes thirteen objects and thirty-two intents', () => {
		expect(PAGE_OBJECTS).toHaveLength(13);
		expect(INTENT_IDS).toHaveLength(32);
		expect(listObjects()).toHaveLength(13);
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

	it('accepts advisory-shape stress blocks beyond catalogue maxima', () => {
		const doc = JSON.parse(readFileSync(join(root, 'fixtures/oversized-stress.json'), 'utf8'));
		const issues = validateDocument(doc);
		expect(issues.filter((issue) => issue.severity === 'error')).toEqual([]);
		const blocks = doc.sections[0].blocks;
		const equation = blocks.find((block: { id: string }) => block.id === 'stress-equation-five-inputs');
		expect(equation?.content.inputs).toHaveLength(5);
		expect(equation?.content.outputs).toHaveLength(4);
		const compare = blocks.find((block: { id: string }) => block.id === 'stress-compare-four');
		expect(compare?.content.items).toHaveLength(4);
	});

	it('treats heading as structural (no intent compatibility)', () => {
		expect(isCompatible('heading', 'orient')).toBe(false);
		expect(isCompatible('aside', 'warn')).toBe(true);
		expect(isCompatible('prose', 'answer-key')).toBe(false);
	});
});
