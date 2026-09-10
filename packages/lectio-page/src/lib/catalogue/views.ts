import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import intentCatalogue from '../../../contracts/intent-catalogue.v1.json';
import objectCatalogue from '../../../contracts/object-catalogue.v1.json';
import documentSchema from '../../../contracts/lectio-document-v2.schema.json';
import type { IntentRecord } from './compatibility';
import type { CapacityLimits, ObjectRecord } from './objects';

export const SELECTION_VIEW_VERSION = '1.0.0';
export const WRITER_VIEW_VERSION = '2.0.0';
export const INTENT_OBJECT_MAP_VERSION = '1.0.0';
export const AUTHORING_DEFINITION_VERSION = '2.0.0';

/**
 * The two catalogues plus the document schema, passed explicitly so the
 * exporter and the regeneration gate can drive these projections from any
 * revision instead of only the committed one.
 */
export interface CatalogueSource {
	intents: Record<string, IntentRecord>;
	objects: Record<string, ObjectRecord>;
	intent_catalogue_version: string;
	object_catalogue_version: string;
	document_schema: JsonObject;
	authoring_resource_root?: string;
}

type JsonObject = Record<string, unknown>;
type AuthoringMode = 'generate' | 'convert-approved';

export interface AuthoringInstructions {
	resource_ref: string;
	text: string;
}

const PRINT_INSTRUCTION_RESOURCES: Record<string, string> = {
	prose: 'contracts/authoring/instructions/prose-writer-v1.txt',
	list: 'contracts/authoring/instructions/list-writer-v1.txt',
	table: 'contracts/authoring/instructions/table-writer-v1.txt',
	figure: 'contracts/authoring/instructions/figure-brief-writer-v1.txt',
	aside: 'contracts/authoring/instructions/aside-writer-v1.txt',
	'worked-example': 'contracts/authoring/instructions/worked-example-writer-v1.txt',
	questions: 'contracts/authoring/instructions/questions-converter-v1.txt',
	choices: 'contracts/authoring/instructions/choices-converter-v1.txt',
	heading: 'contracts/authoring/instructions/heading-system-v1.txt',
	'answer-key': 'contracts/authoring/instructions/answer-key-system-v1.txt'
};

const PRINT_VALIDATOR_REFS = new Set([
	'print.payload_schema',
	'print.validate_content',
	'print.validate_answer_key_integrity'
]);

function defaultContractsRoot(): string {
	if (import.meta.url.startsWith('file:')) {
		try {
			return fileURLToPath(new URL('../../../contracts', import.meta.url));
		} catch {
			// Vitest can rewrite import.meta.url on Windows; package tests run from package root.
		}
	}
	return join(process.cwd(), 'contracts');
}

export function catalogueSource(): CatalogueSource {
	return {
		intents: intentCatalogue.intents as unknown as Record<string, IntentRecord>,
		objects: objectCatalogue.objects as unknown as Record<string, ObjectRecord>,
		intent_catalogue_version: intentCatalogue.catalogue_version,
		object_catalogue_version: objectCatalogue.catalogue_version,
		document_schema: documentSchema as unknown as JsonObject,
		authoring_resource_root: defaultContractsRoot()
	};
}

// ── Reverse compatibility maps ──────────────────────────────────────────────

export interface IntentObjectMap {
	view: 'intent-object-map';
	view_version: string;
	intent_catalogue_version: string;
	object_catalogue_version: string;
	/** Authored direction, copied verbatim from the intent catalogue. */
	intent_to_objects: Record<string, string[]>;
	/** Generated direction. Never hand-maintained. */
	object_to_intents: Record<string, string[]>;
	/** Generated: selectable intents against form-selectable objects only. */
	selectable_intent_to_forms: Record<string, string[]>;
}

export function buildIntentObjectMap(source: CatalogueSource = catalogueSource()): IntentObjectMap {
	const intent_to_objects: Record<string, string[]> = {};
	const object_to_intents: Record<string, string[]> = {};
	const selectable_intent_to_forms: Record<string, string[]> = {};

	for (const objectId of Object.keys(source.objects)) {
		object_to_intents[objectId] = [];
	}

	for (const [intentId, record] of Object.entries(source.intents)) {
		const objects = [...record.valid_objects];
		intent_to_objects[intentId] = objects;

		for (const objectId of objects) {
			const bucket = object_to_intents[objectId];
			if (!bucket) {
				throw new Error(
					`intent "${intentId}" lists unknown page object "${objectId}"; add it to the object catalogue or fix the intent`
				);
			}
			if (!bucket.includes(intentId)) bucket.push(intentId);
		}

		if (record.selectable !== false) {
			selectable_intent_to_forms[intentId] = objects.filter(
				(objectId) => source.objects[objectId]?.form_selectable === true
			);
		}
	}

	return {
		view: 'intent-object-map',
		view_version: INTENT_OBJECT_MAP_VERSION,
		intent_catalogue_version: source.intent_catalogue_version,
		object_catalogue_version: source.object_catalogue_version,
		intent_to_objects,
		object_to_intents,
		selectable_intent_to_forms
	};
}

// ── Selection view ──────────────────────────────────────────────────────────

export interface FormSelectionRecord {
	id: string;
	purpose: string;
	supported_intents: string[];
	supported_actions: string[];
	choose_when: string;
	reject_when: string;
	capacity: CapacityLimits;
	placement: string[];
	requires_asset: boolean;
	produces_answer_key: boolean;
}

/**
 * Generated selection view: enough to choose a form, and no more.
 *
 * Carries eligible form ids, purpose, supported intents/actions, the
 * choose/reject test and capacity limits. Deliberately absent: `content_schema`,
 * resolved payload schemas, per-field writer guidance and negative cases — those
 * belong to the writer view for the one form that was actually chosen.
 */
export interface FormSelectionView {
	view: 'selection';
	view_version: string;
	intent_catalogue_version: string;
	object_catalogue_version: string;
	forms: FormSelectionRecord[];
	/** Forms present in the catalogue that a selector may never choose, with cause. */
	excluded_forms: Array<{ id: string; reason: string }>;
}

export function buildSelectionView(source: CatalogueSource = catalogueSource()): FormSelectionView {
	const { object_to_intents } = buildIntentObjectMap(source);
	const selectableIntents = new Set(
		Object.entries(source.intents)
			.filter(([, record]) => record.selectable !== false)
			.map(([id]) => id)
	);

	const forms: FormSelectionRecord[] = [];
	const excluded_forms: Array<{ id: string; reason: string }> = [];

	for (const [id, record] of Object.entries(source.objects)) {
		if (record.form_selectable !== true) {
			excluded_forms.push({
				id,
				reason:
					record.not_form_selectable_because ??
					'Marked form_selectable: false in the object catalogue.'
			});
			continue;
		}
		if (!record.earns_its_place_when || !record.reject_when || !record.capacity) {
			throw new Error(
				`form "${id}" is form_selectable but has no earns_its_place_when / reject_when / capacity; complete the object record or mark it unselectable`
			);
		}
		forms.push({
			id,
			purpose: record.holds,
			supported_intents: (object_to_intents[id] ?? []).filter((intentId) =>
				selectableIntents.has(intentId)
			),
			supported_actions: [...(record.supported_actions ?? [])],
			choose_when: record.earns_its_place_when,
			reject_when: record.reject_when,
			capacity: { ...record.capacity },
			placement: [...record.placement],
			requires_asset: record.requires_asset === true,
			produces_answer_key: record.produces_answer_key === true
		});
	}

	return {
		view: 'selection',
		view_version: SELECTION_VIEW_VERSION,
		intent_catalogue_version: source.intent_catalogue_version,
		object_catalogue_version: source.object_catalogue_version,
		forms,
		excluded_forms
	};
}

// ── Writer view ─────────────────────────────────────────────────────────────

export interface FormWriterRecord {
	id: string;
	definition_version: string;
	capability_id: string;
	native_path: 'print';
	lane: 'content';
	purpose: string;
	modes: AuthoringMode[];
	instructions: AuthoringInstructions;
	schema_ref: string;
	payload_schema_ref: string;
	/** The exact payload subschema, resolved from the document schema. */
	payload_schema: JsonObject;
	/** Shorthand field map kept for humans; `payload_schema` is authoritative. */
	content_schema: Record<string, string>;
	field_guidance: Record<string, string>;
	writer_guidance: Record<string, string>;
	required_inputs: string[];
	negative_cases: string[];
	capacity: CapacityLimits;
	validator_refs: string[];
	converter_ref?: string;
	postprocessor_ref?: string;
	knowledge: {
		default: 'supplied_only' | 'supplied_preferred' | 'objective_development';
		supported: Array<'supplied_only' | 'supplied_preferred' | 'objective_development'>;
	};
	definition_hash: string;
	fragmentation: string;
	emphasis: string;
	placement: string[];
	source_refs: string[];
}

/**
 * Generated writer view: the exact payload contract for one chosen form.
 *
 * Kept separate from the selection view so a writer request can carry the
 * schema for the selected form only, never the whole catalogue.
 */
export interface FormWriterView {
	view: 'writer';
	view_version: string;
	object_catalogue_version: string;
	document_schema_ref: string;
	forms: Record<string, FormWriterRecord>;
}

function resolveLocalRef(root: JsonObject, pointer: string): JsonObject {
	const parts = pointer
		.replace(/^#\//, '')
		.split('/')
		.map((part) => part.replace(/~1/g, '/').replace(/~0/g, '~'));
	let node: unknown = root;
	for (const part of parts) {
		if (!node || typeof node !== 'object') {
			throw new Error(`cannot resolve schema pointer "${pointer}"`);
		}
		node = (node as JsonObject)[part];
	}
	if (!node || typeof node !== 'object') {
		throw new Error(`schema pointer "${pointer}" does not resolve to a schema object`);
	}
	return node as JsonObject;
}

function readPackageResource(resourceRef: string, source: CatalogueSource): string {
	const root =
		source.authoring_resource_root ??
		defaultContractsRoot();
	const relative = resourceRef.replace(/^contracts\//, '');
	try {
		return readFileSync(join(root, relative), 'utf8').trim();
	} catch (error) {
		throw new Error(`authoring instruction resource missing: ${resourceRef}`, {
			cause: error
		});
	}
}

function instructionFor(id: string, source: CatalogueSource): AuthoringInstructions {
	const resource_ref = PRINT_INSTRUCTION_RESOURCES[id];
	if (!resource_ref) {
		throw new Error(`no authoring instruction resource registered for print/${id}`);
	}
	return { resource_ref, text: readPackageResource(resource_ref, source) };
}

function modesFor(id: string): AuthoringMode[] {
	return id === 'questions' || id === 'choices' || id === 'answer-key'
		? ['convert-approved']
		: ['generate'];
}

function requiredInputsFor(id: string): string[] {
	const base = [
		'teaching_plan_block',
		'form_selection_decision',
		'lesson_context',
		'allowed_facts',
		'terminology'
	];
	if (id === 'questions' || id === 'choices' || id === 'answer-key') {
		return [...base, 'approved_assessment_items'];
	}
	return base;
}

function knowledgeFor(id: string): {
	default: 'supplied_only' | 'supplied_preferred' | 'objective_development';
	supported: Array<'supplied_only' | 'supplied_preferred' | 'objective_development'>;
} {
	if (id === 'questions' || id === 'choices' || id === 'answer-key') {
		return { default: 'supplied_only', supported: ['supplied_only'] };
	}
	return {
		default: 'supplied_preferred',
		supported: ['supplied_only', 'supplied_preferred', 'objective_development']
	};
}

function validatorRefsFor(id: string): string[] {
	const refs = ['print.payload_schema', 'print.validate_content'];
	if (id === 'questions' || id === 'choices' || id === 'answer-key') {
		refs.push('print.validate_answer_key_integrity');
	}
	for (const ref of refs) {
		if (!PRINT_VALIDATOR_REFS.has(ref)) {
			throw new Error(`unknown validator_ref "${ref}" for print/${id}`);
		}
	}
	return refs;
}

function stableStringify(value: unknown): string {
	if (Array.isArray(value)) {
		return `[${value.map(stableStringify).join(',')}]`;
	}
	if (value && typeof value === 'object') {
		return `{${Object.entries(value as Record<string, unknown>)
			.filter(([, child]) => child !== undefined)
			.sort(([a], [b]) => a.localeCompare(b))
			.map(([key, child]) => `${JSON.stringify(key)}:${stableStringify(child)}`)
			.join(',')}}`;
	}
	return JSON.stringify(value);
}

function hashDefinition(payload: Record<string, unknown>): string {
	return createHash('sha256').update(stableStringify(payload)).digest('hex');
}

export function buildWriterRecord(
	id: string,
	source: CatalogueSource = catalogueSource()
): FormWriterRecord {
	const record = source.objects[id];
	if (!record) throw new Error(`unknown page object "${id}"`);
	if (!record.payload_schema_ref) {
		throw new Error(`object "${id}" has no payload_schema_ref`);
	}
	const [schemaFile, pointer] = record.payload_schema_ref.split('#');
	if (!pointer) {
		throw new Error(`payload_schema_ref for "${id}" has no JSON pointer fragment`);
	}

	const missingGuidance = Object.keys(record.content_schema).filter(
		(field) => !record.writer_guidance?.[field]
	);
	if (missingGuidance.length > 0) {
		throw new Error(
			`object "${id}" has no writer guidance for: ${missingGuidance.join(', ')}`
		);
	}

	const instructions = instructionFor(id, source);
	const fieldGuidance = { ...record.writer_guidance };
	const validator_refs = validatorRefsFor(id);
	const schema_ref = record.payload_schema_ref;
	const payload_schema = resolveLocalRef(source.document_schema, `#${pointer}`);
	const knowledge = knowledgeFor(id);
	const definitionPayload = {
		definition_version: AUTHORING_DEFINITION_VERSION,
		capability_id: id,
		native_path: 'print',
		lane: 'content',
		purpose: record.holds,
		modes: modesFor(id),
		instructions,
		schema_ref,
		payload_schema,
		field_guidance: fieldGuidance,
		required_inputs: requiredInputsFor(id),
		capacity: { ...(record.capacity ?? {}) },
		negative_cases: [...(record.negative_cases ?? [])],
		validator_refs,
		knowledge,
		converter_ref:
			id === 'questions' || id === 'choices'
				? 'print.approved_assessment_converter'
				: undefined,
		postprocessor_ref: id === 'figure' ? 'print.figure_asset_postprocessor' : undefined,
		fragmentation: record.fragmentation,
		emphasis: record.emphasis,
		placement: [...record.placement]
	};

	return {
		id,
		definition_version: AUTHORING_DEFINITION_VERSION,
		capability_id: id,
		native_path: 'print',
		lane: 'content',
		purpose: record.holds,
		modes: modesFor(id),
		instructions,
		schema_ref,
		payload_schema_ref: record.payload_schema_ref,
		payload_schema,
		content_schema: { ...record.content_schema },
		field_guidance: fieldGuidance,
		writer_guidance: fieldGuidance,
		required_inputs: requiredInputsFor(id),
		negative_cases: [...(record.negative_cases ?? [])],
		capacity: { ...(record.capacity ?? {}) },
		validator_refs,
		knowledge,
		...(definitionPayload.converter_ref ? { converter_ref: definitionPayload.converter_ref } : {}),
		...(definitionPayload.postprocessor_ref
			? { postprocessor_ref: definitionPayload.postprocessor_ref }
			: {}),
		definition_hash: hashDefinition(definitionPayload),
		fragmentation: record.fragmentation,
		emphasis: record.emphasis,
		placement: [...record.placement],
		source_refs: [
			`object-catalogue.v1.json#/objects/${id}`,
			`${schemaFile}#${pointer}`
		]
	};
}

export function buildWriterView(source: CatalogueSource = catalogueSource()): FormWriterView {
	const forms: Record<string, FormWriterRecord> = {};
	for (const id of Object.keys(source.objects)) {
		forms[id] = buildWriterRecord(id, source);
	}
	return {
		view: 'writer',
		view_version: WRITER_VIEW_VERSION,
		object_catalogue_version: source.object_catalogue_version,
		document_schema_ref: 'lectio-document-v2.schema.json',
		forms
	};
}
