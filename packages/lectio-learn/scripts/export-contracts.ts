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
 *   {out}/learn-capabilities.v1.json - the capability catalogue (all records)
 *   {out}/learn-teaching-view.v1.json - shared vocabulary coverage, no native ids
 *   {out}/learn-selection-view.v1.json - selectable capabilities, no payloads
 *   {out}/learn-writer-view.v1.json - payload schema + guidance per capability
 *   {out}/learn-runtime-view.v1.json - response schema + evaluator per capability
 *   {out}/learn-capability-manifest.json - versions and hashes of the above
 *
 * The pipeline reads these files. It never imports from src/.
 * Single source of truth stays here in TypeScript.
 */

import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { createGenerator } from 'ts-json-schema-generator';
import { validateAllLectioContentModules } from '../src/lib/lectio/core/validate-component';
import { lectioComponentModules } from '../src/lib/schema/registry';
import { buildLectioContentContract } from '../src/lib/lectio/build-content-contract';
import {
	CAPABILITY_CATALOGUE_VERSION,
	learnCapabilities,
	validateCapabilityRecords
} from '../src/lib/learn/capabilities';
import {
	buildRuntimeView,
	buildSelectionView,
	buildTeachingView,
	buildWriterView,
	AUTHORING_DEFINITION_VERSION,
	RUNTIME_VIEW_VERSION,
	SELECTION_VIEW_VERSION,
	TEACHING_VIEW_VERSION,
	WRITER_VIEW_VERSION
} from '../src/lib/learn/capabilities/views';
import {
	MANIFEST_VERSION,
	manifestEntry,
	type CapabilityManifest,
	type ManifestEntry
} from '../src/lib/learn/capabilities/manifest';

const outArgIndex = process.argv.indexOf('--out');
const outFromArg = outArgIndex !== -1 ? process.argv[outArgIndex + 1] : null;
const outFromEnv = process.env.LECTIO_CONTRACTS_DIR ?? null;
const OUT = resolve(outFromArg ?? outFromEnv ?? 'contracts');
mkdirSync(OUT, { recursive: true });
const packageJson = JSON.parse(readFileSync(resolve('package.json'), 'utf8')) as {
	version: string;
};

type JsonObject = Record<string, unknown>;

function listFiles(dir: string, prefix: string): string[] {
	if (!existsSync(dir)) return [];
	const out: string[] = [];
	for (const entry of readdirSync(dir, { withFileTypes: true })) {
		const rel = `${prefix}/${entry.name}`;
		const full = join(dir, entry.name);
		if (entry.isDirectory()) {
			out.push(...listFiles(full, rel));
		} else {
			out.push(rel);
		}
	}
	return out.sort();
}

function copyAuthoringResources(outDir: string): ManifestEntry[] {
	const sourceRoot = resolve('contracts/authoring');
	const files = listFiles(sourceRoot, 'authoring');
	const entries: ManifestEntry[] = [];
	for (const file of files) {
		const source = resolve('contracts', file);
		const target = resolve(outDir, file);
		mkdirSync(dirname(target), { recursive: true });
		if (source !== target) copyFileSync(source, target);
		const serialized = readFileSync(target, 'utf8');
		entries.push(manifestEntry(file, 'authoring-resource', AUTHORING_DEFINITION_VERSION, serialized));
	}
	return entries;
}

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

function getSectionContentSchema(schemaJson: JsonObject): JsonObject {
	const defs = ((schemaJson.$defs ?? schemaJson.definitions ?? {}) as JsonObject) ?? {};
	return typeof schemaJson.$ref === 'string'
		? resolveLocalRef(schemaJson, schemaJson.$ref as string)
		: ((defs.SectionContent as JsonObject | undefined) ?? schemaJson);
}

const sectionContentSchema = getSectionContentSchema(sectionSchema as JsonObject);
const sectionProps = (sectionContentSchema.properties as JsonObject | undefined) ?? {};
const unifiedContract = buildLectioContentContract(sectionProps, packageJson.version);
writeFileSync(`${OUT}/lectio-content-contract.json`, JSON.stringify(unifiedContract, null, 2));

// ── Capability catalogue and generated views ────────────────────────────────

const capabilityErrors = validateCapabilityRecords(learnCapabilities);
if (capabilityErrors.length > 0) {
	// eslint-disable-next-line no-console
	console.error('[Lectio] Capability catalogue validation failed:');
	for (const error of capabilityErrors) {
		// eslint-disable-next-line no-console
		console.error(`- ${error}`);
	}
	process.exit(1);
}

/**
 * A content capability names its payload by reference into the generated
 * SectionContent schema. Resolving it here — rather than duplicating the schema
 * into the record — keeps one source of truth for the payload shape.
 */
const capabilities = learnCapabilities.map((record) => {
	const [file, pointer] = record.payload_schema_ref.split('#');
	if (file !== 'section-content-schema.json' || !pointer) return record;
	// Pointers are relative to the SectionContent subschema, which is where a
	// section field actually lives; the file root is a `$ref` wrapper.
	return {
		...record,
		payload_schema: resolveLocalRef(sectionContentSchema, `#${pointer}`)
	};
});

// An offerable capability must have a real payload schema; a capability that is
// already `unavailable` may legitimately have nothing to resolve yet, and says
// so in its blocking reasons.
const unresolved = capabilities.filter(
	(record) =>
		record.availability !== 'unavailable' && Object.keys(record.payload_schema).length === 0
);
if (unresolved.length > 0) {
	// eslint-disable-next-line no-console
	console.error('[Lectio] Offerable capabilities with an unresolved payload schema:');
	for (const record of unresolved) {
		// eslint-disable-next-line no-console
		console.error(`- ${record.id} (${record.payload_schema_ref})`);
	}
	process.exit(1);
}

const artifacts: ManifestEntry[] = [];

function writeView(file: string, view: string, version: string, payload: unknown): void {
	const serialized = `${JSON.stringify(payload, null, 2)}\n`;
	writeFileSync(`${OUT}/${file}`, serialized);
	artifacts.push(manifestEntry(file, view, version, serialized));
}

writeView('learn-capabilities.v1.json', 'catalogue', CAPABILITY_CATALOGUE_VERSION, {
	view: 'catalogue',
	view_version: CAPABILITY_CATALOGUE_VERSION,
	native_path: 'learn',
	capabilities
});
writeView(
	'learn-teaching-view.v1.json',
	'teaching',
	TEACHING_VIEW_VERSION,
	buildTeachingView(capabilities)
);
writeView(
	'learn-selection-view.v1.json',
	'selection',
	SELECTION_VIEW_VERSION,
	buildSelectionView(capabilities)
);
writeView('learn-writer-view.v1.json', 'writer', WRITER_VIEW_VERSION, buildWriterView(capabilities));
writeView(
	'learn-runtime-view.v1.json',
	'runtime',
	RUNTIME_VIEW_VERSION,
	buildRuntimeView(capabilities)
);
artifacts.push(...copyAuthoringResources(OUT));

const counts: Record<string, number> = {
	total: capabilities.length,
	interaction: capabilities.filter((record) => record.kind === 'interaction').length,
	content: capabilities.filter((record) => record.kind === 'content').length
};
for (const record of capabilities) {
	counts[`readiness:${record.readiness}`] = (counts[`readiness:${record.readiness}`] ?? 0) + 1;
	counts[`availability:${record.availability}`] =
		(counts[`availability:${record.availability}`] ?? 0) + 1;
}

const manifest: CapabilityManifest = {
	manifest_version: MANIFEST_VERSION,
	catalogue_version: CAPABILITY_CATALOGUE_VERSION,
	package_version: packageJson.version,
	generated_at: new Date().toISOString(),
	capability_counts: counts,
	artifacts
};
writeFileSync(
	`${OUT}/learn-capability-manifest.json`,
	`${JSON.stringify(manifest, null, 2)}\n`
);

console.log('Exported SectionContent schema');
console.log('Exported lectio-content-contract.json');
console.log(`Exported ${artifacts.length} capability artifact(s) for ${capabilities.length} capabilities`);
console.log(`Output: ${OUT}/`);
