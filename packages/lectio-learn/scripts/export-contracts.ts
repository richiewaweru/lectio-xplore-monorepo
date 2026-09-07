/**
 * scripts/export-contracts.ts
 *
 * Exports everything the Python pipeline needs to know about
 * Lectio's templates and components into contracts/.
 *
 * Run this whenever templates, components, or presets change:
 *   npm run export-contracts
 *   LECTIO_CONTRACTS_DIR=/path/to/output npm run export-contracts
 *
 * Output files:
 *   {out}/section-content-schema.json - full SectionContent JSON schema
 *   {out}/lectio-content-contract.json - unified consumer contract surface
 *
 * The pipeline reads these files. It never imports from src/.
 * Single source of truth stays here in TypeScript.
 */

import { mkdirSync, readFileSync, writeFileSync } from 'fs';
import { resolve } from 'path';
import { createGenerator } from 'ts-json-schema-generator';
import { validateAllLectioContentModules } from '../src/lib/lectio/core/validate-component';
import { lectioComponentModules } from '../src/lib/schema/registry';
import { buildLectioContentContract } from '../src/lib/lectio/build-content-contract';

const outArgIndex = process.argv.indexOf('--out');
const outFromArg = outArgIndex !== -1 ? process.argv[outArgIndex + 1] : null;
const outFromEnv = process.env.LECTIO_CONTRACTS_DIR ?? null;
const OUT = resolve(outFromArg ?? outFromEnv ?? 'contracts');
mkdirSync(OUT, { recursive: true });
const packageJson = JSON.parse(readFileSync(resolve('package.json'), 'utf8')) as {
	version: string;
};

type JsonObject = Record<string, unknown>;

const lectioModulesList = Array.from(lectioComponentModules);
const validationIssues = validateAllLectioContentModules(lectioModulesList);
const validationErrors = validationIssues.filter((issue) => issue.severity !== 'warn');
const validationWarnings = validationIssues.filter((issue) => issue.severity === 'warn');
for (const issue of validationWarnings) {
	// eslint-disable-next-line no-console
	console.warn(`[Lectio] Warning ${issue.path}: ${issue.message}`);
}
if (validationErrors.length > 0) {
	// eslint-disable-next-line no-console
	console.error('[Lectio] Component module validation failed:');
	for (const issue of validationErrors) {
		// eslint-disable-next-line no-console
		console.error(`- ${issue.path}: ${issue.message}`);
	}
	process.exit(1);
}

const sectionSchema = createGenerator({
	path: resolve('src/lib/schema/types.ts'),
	tsconfig: resolve('tsconfig.json'),
	type: 'SectionContent',
	additionalProperties: false
}).createSchema('SectionContent');

writeFileSync(`${OUT}/section-content-schema.json`, JSON.stringify(sectionSchema, null, 2));

function resolveLocalRef(root: JsonObject, ref: string): JsonObject {
	const parts = ref
		.replace(/^#\//, '')
		.split('/')
		.map((part) => part.replace(/~1/g, '/').replace(/~0/g, '~'));
	let node: unknown = root;
	for (const part of parts) {
		node = (node as JsonObject)[part];
	}
	return (node ?? {}) as JsonObject;
}

function getSectionContentPropertyMap(schemaJson: JsonObject): JsonObject {
	const defs = ((schemaJson.$defs ?? schemaJson.definitions ?? {}) as JsonObject) ?? {};
	const sectionSchema =
		typeof schemaJson.$ref === 'string'
			? resolveLocalRef(schemaJson, schemaJson.$ref as string)
			: ((defs.SectionContent as JsonObject | undefined) ?? schemaJson);
	return (sectionSchema.properties as JsonObject | undefined) ?? {};
}

const sectionProps = getSectionContentPropertyMap(sectionSchema as JsonObject);
const unifiedContract = buildLectioContentContract(sectionProps, packageJson.version);
writeFileSync(`${OUT}/lectio-content-contract.json`, JSON.stringify(unifiedContract, null, 2));

console.log('Exported SectionContent schema');
console.log('Exported lectio-content-contract.json');
console.log(`Output: ${OUT}/`);
