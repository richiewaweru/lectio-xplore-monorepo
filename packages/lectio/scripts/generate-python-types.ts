/**
 * scripts/generate-python-types.ts
 *
 * Generates official Python Pydantic models from the exported
 * SectionContent JSON schema.
 */

import { mkdirSync, readFileSync, writeFileSync } from 'fs';
import { dirname, resolve } from 'path';

type JsonSchema = Record<string, unknown>;

const PYTHON_KEYWORDS = new Set([
	'False',
	'None',
	'True',
	'and',
	'as',
	'assert',
	'async',
	'await',
	'break',
	'class',
	'continue',
	'def',
	'del',
	'elif',
	'else',
	'except',
	'finally',
	'for',
	'from',
	'global',
	'if',
	'import',
	'in',
	'is',
	'lambda',
	'nonlocal',
	'not',
	'or',
	'pass',
	'raise',
	'return',
	'try',
	'while',
	'with',
	'yield'
]);

function getArgValue(flag: string): string | null {
	const index = process.argv.indexOf(flag);
	if (index === -1) return null;
	return process.argv[index + 1] ?? null;
}

function toPascalCase(value: string): string {
	return value
		.replace(/^[^A-Za-z0-9]+/, '')
		.replace(/[^A-Za-z0-9]+(.)/g, (_, char: string) => char.toUpperCase())
		.replace(/^[a-z]/, (char) => char.toUpperCase())
		.replace(/[^A-Za-z0-9]/g, '') || 'GeneratedModel';
}

function sanitizeIdentifier(value: string): string {
	let out = value.replace(/[^A-Za-z0-9_]/g, '_');
	if (!/^[A-Za-z_]/.test(out)) out = `field_${out}`;
	if (PYTHON_KEYWORDS.has(out)) out = `${out}_field`;
	return out;
}

function decodeJsonPointer(pointer: string): string {
	return pointer.replace(/~1/g, '/').replace(/~0/g, '~');
}

function dedupe<T>(items: T[]): T[] {
	return [...new Set(items)];
}

const schemaFromArg = getArgValue('--schema');
const schemaFromEnv = process.env.LECTIO_SECTION_SCHEMA ?? null;
const outFromArg = getArgValue('--out');
const outFromEnv = process.env.LECTIO_PYTHON_TYPES_OUT ?? null;

const schemaPath = resolve(schemaFromArg ?? schemaFromEnv ?? 'contracts/section-content-schema.json');
const outPath = resolve(outFromArg ?? outFromEnv ?? 'generated/python/section_content.py');

const rootSchema = JSON.parse(readFileSync(schemaPath, 'utf8')) as JsonSchema;
const definitions =
	((rootSchema.$defs as JsonSchema | undefined) ??
		(rootSchema.definitions as JsonSchema | undefined) ??
		{}) as Record<string, JsonSchema>;

const classNameByDef = new Map<string, string>();
const classSchemas = new Map<string, JsonSchema>();
const classOrder: string[] = [];
const aliasDefinitions = new Map<string, string>();
const inlineNameCount = new Map<string, number>();

const typingImports = new Set<string>(['Any']);
let usesField = false;

for (const defName of Object.keys(definitions)) {
	classNameByDef.set(defName, toPascalCase(defName));
}
classNameByDef.set('SectionContent', 'SectionContent');

function resolveRef(ref: string): JsonSchema {
	if (!ref.startsWith('#/')) return {};
	const tokens = ref
		.slice(2)
		.split('/')
		.map((token) => decodeJsonPointer(token));
	let node: unknown = rootSchema;
	for (const token of tokens) {
		if (!node || typeof node !== 'object' || !(token in (node as Record<string, unknown>))) {
			return {};
		}
		node = (node as Record<string, unknown>)[token];
	}
	return (node as JsonSchema) ?? {};
}

function isNullSchema(schema: JsonSchema): boolean {
	const type = schema.type;
	return type === 'null';
}

function isObjectClassCandidate(schema: JsonSchema): boolean {
	const normalized = normalizeObjectSchema(schema);
	const maybeProps = normalized.properties as Record<string, unknown> | undefined;
	return Boolean(maybeProps && Object.keys(maybeProps).length > 0);
}

function ensureClass(name: string, schema: JsonSchema): string {
	if (!classSchemas.has(name)) {
		classSchemas.set(name, schema);
		classOrder.push(name);
	}
	return name;
}

function refToClassName(ref: string): string {
	const defKey = ref.split('/').pop() ?? ref;
	if (classNameByDef.has(defKey)) return classNameByDef.get(defKey)!;
	const generatedName = toPascalCase(defKey);
	classNameByDef.set(defKey, generatedName);
	return generatedName;
}

function makeOptional(typeName: string): string {
	if (typeName.startsWith('Optional[')) return typeName;
	typingImports.add('Optional');
	return `Optional[${typeName}]`;
}

function nextInlineClassName(parentName: string, fieldName: string): string {
	const base = `${toPascalCase(parentName)}${toPascalCase(fieldName)}`;
	const count = inlineNameCount.get(base) ?? 0;
	inlineNameCount.set(base, count + 1);
	return count === 0 ? base : `${base}${count + 1}`;
}

function schemaToType(
	schema: JsonSchema | undefined,
	context: { parentName: string; fieldName: string }
): string {
	if (!schema || typeof schema !== 'object') return 'Any';

	if (typeof schema.$ref === 'string') {
		const className = refToClassName(schema.$ref);
		const resolved = resolveRef(schema.$ref);
		if (isObjectClassCandidate(resolved)) {
			ensureClass(className, resolved);
		}
		return className;
	}

	if (Array.isArray(schema.enum) && schema.enum.length > 0) {
		typingImports.add('Literal');
		return `Literal[${schema.enum.map((item) => JSON.stringify(item)).join(', ')}]`;
	}

	if (schema.const !== undefined) {
		typingImports.add('Literal');
		return `Literal[${JSON.stringify(schema.const)}]`;
	}

	const unionSchemas = (schema.anyOf ?? schema.oneOf) as JsonSchema[] | undefined;
	if (unionSchemas && unionSchemas.length > 0) {
		const nonNull = unionSchemas.filter((entry) => !isNullSchema(entry));
		const hasNull = nonNull.length !== unionSchemas.length;
		const rendered = dedupe(nonNull.map((entry) => schemaToType(entry, context)));
		const baseType =
			rendered.length === 0 ? 'Any' : rendered.length === 1 ? rendered[0] : `Union[${rendered.join(', ')}]`;
		if (rendered.length > 1) typingImports.add('Union');
		return hasNull ? makeOptional(baseType) : baseType;
	}

	if (Array.isArray(schema.type) && schema.type.length > 0) {
		const nonNull = schema.type.filter((entry) => entry !== 'null') as string[];
		const hasNull = nonNull.length !== schema.type.length;
		let baseType = 'Any';
		if (nonNull.length === 1) {
			baseType = schemaToType({ ...schema, type: nonNull[0] }, context);
		} else if (nonNull.length > 1) {
			const rendered = dedupe(nonNull.map((entry) => schemaToType({ type: entry }, context)));
			baseType = `Union[${rendered.join(', ')}]`;
			typingImports.add('Union');
		}
		return hasNull ? makeOptional(baseType) : baseType;
	}

	switch (schema.type) {
		case 'string':
			return 'str';
		case 'number':
			return 'float';
		case 'integer':
			return 'int';
		case 'boolean':
			return 'bool';
		case 'array': {
			const itemType = schemaToType(schema.items as JsonSchema | undefined, {
				parentName: context.parentName,
				fieldName: `${context.fieldName}Item`
			});
			return `list[${itemType}]`;
		}
		case 'object': {
			const props = schema.properties as Record<string, JsonSchema> | undefined;
			if (props && Object.keys(props).length > 0) {
				const inlineName = nextInlineClassName(context.parentName, context.fieldName);
				ensureClass(inlineName, schema);
				return inlineName;
			}
			const additional = schema.additionalProperties as JsonSchema | boolean | undefined;
			if (additional && additional !== true) {
				const valueType = schemaToType(additional as JsonSchema, {
					parentName: context.parentName,
					fieldName: `${context.fieldName}Value`
				});
				return `dict[str, ${valueType}]`;
			}
			return 'dict[str, Any]';
		}
		default: {
			const props = schema.properties as Record<string, JsonSchema> | undefined;
			if (props && Object.keys(props).length > 0) {
				const inlineName = nextInlineClassName(context.parentName, context.fieldName);
				ensureClass(inlineName, schema);
				return inlineName;
			}
			return 'Any';
		}
	}
}

function normalizeObjectSchema(schema: JsonSchema): JsonSchema {
	if (!Array.isArray(schema.allOf) || schema.allOf.length === 0) return schema;

	const merged: JsonSchema = { type: 'object', properties: {}, required: [] };
	for (const entry of schema.allOf as JsonSchema[]) {
		const resolved = entry.$ref ? resolveRef(String(entry.$ref)) : entry;
		const props = (resolved.properties as Record<string, JsonSchema> | undefined) ?? {};
		Object.assign(merged.properties as Record<string, JsonSchema>, props);
		const required = (resolved.required as string[] | undefined) ?? [];
		merged.required = dedupe([...(merged.required as string[]), ...required]);
		if (resolved.additionalProperties !== undefined) {
			merged.additionalProperties = resolved.additionalProperties;
		}
	}
	if (schema.additionalProperties !== undefined) {
		merged.additionalProperties = schema.additionalProperties;
	}
	return merged;
}

for (const [defKey, defSchema] of Object.entries(definitions)) {
	const typeName = classNameByDef.get(defKey) ?? toPascalCase(defKey);
	if (isObjectClassCandidate(defSchema)) {
		ensureClass(typeName, defSchema);
	} else {
		aliasDefinitions.set(
			typeName,
			schemaToType(defSchema, { parentName: typeName, fieldName: 'value' })
		);
	}
}

if (typeof rootSchema.$ref === 'string') {
	const resolvedRoot = resolveRef(rootSchema.$ref);
	ensureClass('SectionContent', resolvedRoot);
} else if (isObjectClassCandidate(rootSchema)) {
	ensureClass('SectionContent', rootSchema);
}

const classBlocks: string[] = [];
let classIndex = 0;
while (classIndex < classOrder.length) {
	const className = classOrder[classIndex];
	const rawSchema = classSchemas.get(className) ?? {};
	const schema = normalizeObjectSchema(rawSchema);

	const properties = (schema.properties as Record<string, JsonSchema> | undefined) ?? {};
	const required = new Set((schema.required as string[] | undefined) ?? []);
	const lines: string[] = [];

	if (schema.additionalProperties === false) {
		lines.push(`    model_config = ConfigDict(extra='forbid')`);
	}

	for (const [rawName, propSchema] of Object.entries(properties)) {
		const fieldType = schemaToType(propSchema, {
			parentName: className,
			fieldName: rawName
		});
		const isRequired = required.has(rawName);
		const annotation = isRequired ? fieldType : makeOptional(fieldType);
		const pythonName = sanitizeIdentifier(rawName);
		const aliasNeeded = pythonName !== rawName;

		if (aliasNeeded) usesField = true;

		if (aliasNeeded && isRequired) {
			lines.push(
				`    ${pythonName}: ${annotation} = Field(alias=${JSON.stringify(rawName)})`
			);
			continue;
		}

		if (aliasNeeded && !isRequired) {
			lines.push(
				`    ${pythonName}: ${annotation} = Field(default=None, alias=${JSON.stringify(rawName)})`
			);
			continue;
		}

		if (!isRequired) {
			lines.push(`    ${pythonName}: ${annotation} = None`);
			continue;
		}

		lines.push(`    ${pythonName}: ${annotation}`);
	}

	if (lines.length === 0) {
		lines.push('    pass');
	}

	classBlocks.push(`class ${className}(BaseModel):\n${lines.join('\n')}`);
	classIndex += 1;
}

const orderedClassNames = [
	...classOrder.filter((name) => name !== 'SectionContent'),
	...classOrder.filter((name) => name === 'SectionContent')
];
const orderedClassBlocks = orderedClassNames.map((name) =>
	classBlocks.find((block) => block.startsWith(`class ${name}(`))
).filter(Boolean) as string[];
const orderedAliases = [...aliasDefinitions.entries()]
	.filter(([name]) => !classSchemas.has(name))
	.sort(([left], [right]) => left.localeCompare(right))
	.map(([name, typeName]) => `${name} = ${typeName}`);

const typingList = [...typingImports].sort().join(', ');
const pydanticImports = usesField ? 'from pydantic import BaseModel, ConfigDict, Field' : 'from pydantic import BaseModel, ConfigDict';
const rebuildLines = orderedClassNames.map((name) => `${name}.model_rebuild()`);

const content = [
	'# -- AUTO-GENERATED - DO NOT EDIT -------------------------------------------',
	'# Source: @richiewaweru/lectio src/lib/schema/types.ts',
	'# Generated from: contracts/section-content-schema.json',
	'# Generator: scripts/generate-python-types.ts',
	'# Run `npm run export-contracts` in the Lectio repo to regenerate.',
	'# ---------------------------------------------------------------------------',
	'',
	'from __future__ import annotations',
	'',
	`from typing import ${typingList}`,
	pydanticImports,
	'',
	...orderedClassBlocks,
	'',
	...orderedAliases,
	'',
	...rebuildLines,
	''
].join('\n');

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, content);

console.log(`Generated Python adapter from ${schemaPath}`);
console.log(`Output: ${outPath}`);
