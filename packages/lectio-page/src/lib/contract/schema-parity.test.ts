import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { INTENT_IDS, PAGE_OBJECTS } from '$lib/contract';
import { listIntents, listObjects } from '$lib/catalogue';

const root = process.cwd();
const schema = JSON.parse(
	readFileSync(join(root, 'contracts/lectio-document-v2.schema.json'), 'utf8')
);
const intentCatalogue = JSON.parse(
	readFileSync(join(root, 'contracts/intent-catalogue.v1.json'), 'utf8')
);
const objectCatalogue = JSON.parse(
	readFileSync(join(root, 'contracts/object-catalogue.v1.json'), 'utf8')
);

describe('contract export parity', () => {
	it('keeps page-object constants aligned with catalogues and schema', () => {
		expect(PAGE_OBJECTS).toHaveLength(10);
		expect(listObjects().sort()).toEqual([...PAGE_OBJECTS].sort());
		expect(Object.keys(objectCatalogue.objects).sort()).toEqual([...PAGE_OBJECTS].sort());

		const blockOneOf = schema.$defs.block.oneOf as Array<{ $ref: string }>;
		expect(blockOneOf).toHaveLength(10);

		expect(INTENT_IDS).toHaveLength(32);
		expect(listIntents().sort()).toEqual([...INTENT_IDS].sort());
		expect(Object.keys(intentCatalogue.intents).sort()).toEqual([...INTENT_IDS].sort());
		expect(schema.$defs['intent-id'].enum.sort()).toEqual([...INTENT_IDS].sort());
	});

	it('defines exact block schemas without generic content', () => {
		expect(schema.$defs['heading-block'].properties.intent).toBeUndefined();
		expect(schema.$defs['heading-block'].required).not.toContain('intent');
		expect(schema.$defs['prose-block'].properties.content.$ref).toBe('#/$defs/prose-content');
		expect(schema.$defs['questions-block'].properties.content.$ref).toBe(
			'#/$defs/questions-content'
		);
	});
});
