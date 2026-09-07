import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv from 'ajv';
import { LEARNER_ACTION_IDS } from '@lectio/contracts';
import { INTENT_IDS, PAGE_OBJECTS, type IntentId, type PageObject } from '$lib/contract';
import {
	buildIntentObjectMap,
	buildSelectionView,
	buildWriterRecord,
	buildWriterView,
	catalogueSource,
	getIntent,
	getObject,
	isSelectable,
	listSelectableIntents
} from '$lib/catalogue';

const root = process.cwd();
const documentSchema = JSON.parse(
	readFileSync(join(root, 'contracts/lectio-document-v2.schema.json'), 'utf8')
);
const fixture = JSON.parse(
	readFileSync(join(root, 'fixtures/photosynthesis-ref.json'), 'utf8')
) as {
	sections: Array<{ blocks: Array<{ object: PageObject; content: unknown }> }>;
	answer_key?: { object: PageObject; content: unknown };
};

const FORM_SELECTABLE = [
	'prose',
	'list',
	'table',
	'figure',
	'aside',
	'worked-example',
	'questions',
	'choices'
] as const;

function collectKeys(value: unknown, into = new Set<string>()): Set<string> {
	if (Array.isArray(value)) {
		for (const item of value) collectKeys(item, into);
	} else if (value && typeof value === 'object') {
		for (const [key, child] of Object.entries(value)) {
			into.add(key);
			collectKeys(child, into);
		}
	}
	return into;
}

describe('P01-K02 — object records are complete and every ref resolves', () => {
	it('declares form selectability for every page object, with a reason when false', () => {
		for (const id of PAGE_OBJECTS) {
			const record = getObject(id);
			expect(typeof record?.form_selectable, `object ${id}`).toBe('boolean');
			if (record?.form_selectable === false) {
				expect(record.not_form_selectable_because, `object ${id}`).toBeTruthy();
			}
		}
		expect(PAGE_OBJECTS.filter((id) => getObject(id)?.form_selectable === true).sort()).toEqual(
			[...FORM_SELECTABLE].sort()
		);
	});

	it('gives every generation-ready form choose/reject/capacity plus writer guidance', () => {
		for (const id of FORM_SELECTABLE) {
			const record = getObject(id)!;
			expect(record.earns_its_place_when, `${id} choose_when`).toBeTruthy();
			expect(record.reject_when, `${id} reject_when`).toBeTruthy();
			expect(record.capacity, `${id} capacity`).toBeTruthy();
			expect(record.negative_cases?.length, `${id} negative_cases`).toBeGreaterThan(0);
			for (const field of Object.keys(record.content_schema)) {
				expect(
					record.writer_guidance?.[field],
					`${id} has no writer guidance for field "${field}"`
				).toBeTruthy();
			}
		}
	});

	it('gives writer guidance to the two non-selectable objects too', () => {
		for (const id of ['heading', 'answer-key'] as const) {
			const record = getObject(id)!;
			for (const field of Object.keys(record.content_schema)) {
				expect(record.writer_guidance?.[field], `${id}.${field}`).toBeTruthy();
			}
		}
	});

	it('resolves every payload_schema_ref against the document schema', () => {
		for (const id of PAGE_OBJECTS) {
			const ref = getObject(id)?.payload_schema_ref;
			expect(ref, `object ${id} payload_schema_ref`).toBe(
				`lectio-document-v2.schema.json#/$defs/${id}-content`
			);
			expect(documentSchema.$defs[`${id}-content`]).toBeTruthy();
		}
	});

	it('resolves every supported_action against the shared learner-action vocabulary', () => {
		const known = new Set<string>(LEARNER_ACTION_IDS);
		for (const id of PAGE_OBJECTS) {
			const actions = getObject(id)?.supported_actions;
			expect(Array.isArray(actions), `object ${id} supported_actions`).toBe(true);
			for (const action of actions!) {
				expect(known.has(action), `object ${id} names unknown learner action "${action}"`).toBe(
					true
				);
			}
			expect(new Set(actions).size, `object ${id} duplicate actions`).toBe(actions!.length);
		}
		expect(getObject('choices')?.supported_actions).toEqual(['select-one']);
		expect(getObject('heading')?.supported_actions).toEqual([]);
	});

	it('resolves every intent valid_object against the object catalogue', () => {
		for (const id of INTENT_IDS) {
			for (const objectId of getIntent(id)!.valid_objects) {
				expect(getObject(objectId), `intent ${id} names unknown object ${objectId}`).toBeTruthy();
			}
		}
	});

	it('generates the object→intent reverse map consistently with the authored direction', () => {
		const map = buildIntentObjectMap();
		expect(Object.keys(map.intent_to_objects).sort()).toEqual([...INTENT_IDS].sort());
		expect(Object.keys(map.object_to_intents).sort()).toEqual([...PAGE_OBJECTS].sort());

		for (const [intentId, objects] of Object.entries(map.intent_to_objects)) {
			for (const objectId of objects) {
				expect(
					map.object_to_intents[objectId],
					`${objectId} reverse map missing ${intentId}`
				).toContain(intentId);
			}
		}
		for (const [objectId, intents] of Object.entries(map.object_to_intents)) {
			for (const intentId of intents) {
				expect(map.intent_to_objects[intentId]).toContain(objectId);
			}
		}

		expect(map.object_to_intents.heading).toEqual([]);
		expect(map.object_to_intents['answer-key']).toEqual(['answer-key']);
		expect(map.selectable_intent_to_forms['answer-key']).toBeUndefined();
		expect(map.selectable_intent_to_forms.compare).toEqual(['table', 'prose', 'questions']);
	});

	it('validates the reference fixture against the exact per-object payload schemas', () => {
		const ajv = new Ajv({ strict: false, allErrors: true });
		const blocks = [
			...fixture.sections.flatMap((section) => section.blocks),
			...(fixture.answer_key ? [fixture.answer_key] : [])
		];
		expect(blocks.length).toBeGreaterThan(9);

		const seen = new Set<string>();
		for (const block of blocks) {
			const record = buildWriterRecord(block.object);
			const validate = ajv.compile({
				...record.payload_schema,
				$defs: documentSchema.$defs
			});
			const ok = validate(block.content);
			expect(ok, `${block.object}: ${ajv.errorsText(validate.errors)}`).toBe(true);
			seen.add(block.object);
		}
		expect([...seen].sort()).toEqual([...PAGE_OBJECTS].sort());
	});
});

describe('P01-K06 — selection and writer views stay separated', () => {
	const selection = buildSelectionView();
	const writer = buildWriterView();

	it('offers exactly the form-selectable objects, with the rest excluded and explained', () => {
		expect(selection.forms.map((form) => form.id).sort()).toEqual([...FORM_SELECTABLE].sort());
		expect(selection.excluded_forms.map((form) => form.id).sort()).toEqual([
			'answer-key',
			'heading'
		]);
		for (const excluded of selection.excluded_forms) {
			expect(excluded.reason).toBeTruthy();
		}
	});

	it('carries no payload schema, writer guidance or negative cases', () => {
		const keys = collectKeys(selection);
		for (const banned of [
			'content_schema',
			'payload_schema',
			'payload_schema_ref',
			'writer_guidance',
			'negative_cases',
			'fragmentation',
			'emphasis'
		]) {
			expect(keys.has(banned), `selection view leaks "${banned}"`).toBe(false);
		}
	});

	it('exposes only selection fields per form', () => {
		for (const form of selection.forms) {
			expect(Object.keys(form).sort()).toEqual([
				'capacity',
				'choose_when',
				'id',
				'placement',
				'produces_answer_key',
				'purpose',
				'reject_when',
				'requires_asset',
				'supported_actions',
				'supported_intents'
			]);
		}
	});

	it('lists only selectable intents against each form', () => {
		const selectable = new Set<string>(listSelectableIntents());
		for (const form of selection.forms) {
			for (const intentId of form.supported_intents) {
				expect(selectable.has(intentId), `${form.id} offers unselectable ${intentId}`).toBe(
					true
				);
				expect(getIntent(intentId as IntentId)!.valid_objects).toContain(form.id);
			}
		}
		expect(isSelectable('answer-key')).toBe(false);
	});

	it('flags asset and answer-key obligations so a selector can respect them', () => {
		const byId = new Map(selection.forms.map((form) => [form.id, form]));
		expect(byId.get('figure')?.requires_asset).toBe(true);
		expect(byId.get('prose')?.requires_asset).toBe(false);
		expect(byId.get('questions')?.produces_answer_key).toBe(true);
		expect(byId.get('choices')?.produces_answer_key).toBe(true);
		expect(byId.get('table')?.produces_answer_key).toBe(false);
	});

	it('keeps the exact payload contract in the writer view instead', () => {
		expect(Object.keys(writer.forms).sort()).toEqual([...PAGE_OBJECTS].sort());
		for (const id of PAGE_OBJECTS) {
			const record = writer.forms[id];
			expect(record.payload_schema.type).toBe('object');
			expect(record.payload_schema.additionalProperties).toBe(false);
			expect(Object.keys(record.writer_guidance).length).toBeGreaterThan(0);
			expect(record.source_refs).toContain(`object-catalogue.v1.json#/objects/${id}`);
		}
	});

	it('refuses to build a writer record when field guidance is missing', () => {
		const source = structuredClone(catalogueSource());
		delete source.objects.table!.writer_guidance!.rows;
		expect(() => buildWriterRecord('table', source)).toThrow(/no writer guidance for: rows/);
	});

	it('refuses to offer a form that is selectable but incomplete', () => {
		const source = structuredClone(catalogueSource());
		delete source.objects.list!.capacity;
		expect(() => buildSelectionView(source)).toThrow(/form "list" is form_selectable/);
	});

	it('fails loudly when an intent names an object that does not exist', () => {
		const source = structuredClone(catalogueSource());
		source.intents.compare!.valid_objects = ['table', 'flowchart'] as never;
		expect(() => buildIntentObjectMap(source)).toThrow(/unknown page object "flowchart"/);
	});
});
