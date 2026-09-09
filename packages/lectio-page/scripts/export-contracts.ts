/**
 * scripts/export-contracts.ts
 *
 * Publishes the Print contract surface: the hand-authored catalogues and schema,
 * plus the generated selection / writer / reverse-map views, hashed into
 * contracts/manifest.json.
 *
 *   pnpm --filter @lectio/page export-contracts
 *   tsx scripts/export-contracts.ts --source-dir <contracts dir> --out <dir>
 *
 * `--source-dir` and `--out` exist so the regeneration gate can drive this exact
 * exporter against a mutated catalogue copy without touching the committed
 * files. `generated_at` is the only non-reproducible field in the output.
 */

import { createHash } from 'node:crypto';
import {
	copyFileSync,
	existsSync,
	mkdirSync,
	readdirSync,
	readFileSync,
	writeFileSync
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
	buildIntentObjectMap,
	buildSelectionView,
	buildWriterView,
	type CatalogueSource
} from '../src/lib/catalogue/views';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

const AUTHORED_FILES = [
	'lectio-document-v2.schema.json',
	'object-catalogue.v1.json',
	'intent-catalogue.v1.json',
	'base-print.css'
] as const;

const GENERATED_FILES = [
	'generated/form-selection-view.v1.json',
	'generated/form-writer-view.v1.json',
	'generated/intent-object-map.v1.json'
] as const;

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

function argValue(flag: string): string | null {
	const index = process.argv.indexOf(flag);
	if (index === -1) return null;
	return process.argv[index + 1] ?? null;
}

type JsonObject = Record<string, unknown>;

/** Reads the catalogue triple from disk so any revision can be projected. */
export function readCatalogueSource(sourceDir: string): CatalogueSource {
	const read = (name: string) => JSON.parse(readFileSync(join(sourceDir, name), 'utf8'));
	const intentCatalogue = read('intent-catalogue.v1.json');
	const objectCatalogue = read('object-catalogue.v1.json');
	return {
		intents: intentCatalogue.intents,
		objects: objectCatalogue.objects,
		intent_catalogue_version: intentCatalogue.catalogue_version,
		object_catalogue_version: objectCatalogue.catalogue_version,
		document_schema: read('lectio-document-v2.schema.json') as JsonObject,
		authoring_resource_root: sourceDir
	};
}

export function exportContracts(sourceDir: string, outDir: string): void {
	mkdirSync(outDir, { recursive: true });
	mkdirSync(join(outDir, 'generated'), { recursive: true });
	mkdirSync(join(outDir, 'authoring', 'instructions'), { recursive: true });

	// base-print.css source of truth is src/lib/print/ — that is the path exported
	// from package.json. Sync it into the contracts dir before hashing so
	// manifest.json attests to the file consumers actually load.
	copyFileSync(join(root, 'src/lib/print/base-print.css'), join(outDir, 'base-print.css'));

	for (const name of AUTHORED_FILES) {
		if (name === 'base-print.css') continue;
		const from = join(sourceDir, name);
		const to = join(outDir, name);
		if (resolve(from) !== resolve(to)) copyFileSync(from, to);
	}

	const instructionFiles = listFiles(join(sourceDir, 'authoring'), 'authoring');
	for (const name of instructionFiles) {
		const from = join(sourceDir, name);
		const to = join(outDir, name);
		mkdirSync(dirname(to), { recursive: true });
		if (resolve(from) !== resolve(to)) copyFileSync(from, to);
	}

	const source = readCatalogueSource(sourceDir);
	const views: Array<[string, unknown]> = [
		['generated/form-selection-view.v1.json', buildSelectionView(source)],
		['generated/form-writer-view.v1.json', buildWriterView(source)],
		['generated/intent-object-map.v1.json', buildIntentObjectMap(source)]
	];
	for (const [name, view] of views) {
		writeFileSync(join(outDir, name), JSON.stringify(view, null, 2) + '\n');
	}

	const entries = [...AUTHORED_FILES, ...instructionFiles, ...GENERATED_FILES].map((name) => {
		const bytes = readFileSync(join(outDir, name));
		return {
			path: name,
			sha256: createHash('sha256').update(bytes).digest('hex'),
			bytes: bytes.byteLength
		};
	});

	const manifest = {
		manifest_version: '1.1.0',
		package: '@lectio/page',
		contract_version: '1.1.0',
		intent_catalogue_version: source.intent_catalogue_version,
		object_catalogue_version: source.object_catalogue_version,
		generated_at: new Date().toISOString(),
		files: entries
	};

	writeFileSync(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');

	// Keep the architecture pack contracts in sync with the published schema.
	const packDir = join(root, 'docs/architecture/page-objects/contracts');
	if (existsSync(packDir)) {
		copyFileSync(
			join(outDir, 'lectio-document-v2.schema.json'),
			join(packDir, 'lectio-document-v2.schema.json')
		);
		copyFileSync(join(outDir, 'base-print.css'), join(packDir, 'base-print.css'));
	}

	console.log('Exported contracts + generated views + manifest.json');
	for (const entry of entries) {
		console.log(`  ${entry.path}  ${entry.sha256.slice(0, 12)}…  ${entry.bytes}b`);
	}
}

const invokedDirectly =
	process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (invokedDirectly) {
	const sourceDir = resolve(argValue('--source-dir') ?? join(root, 'contracts'));
	exportContracts(sourceDir, resolve(argValue('--out') ?? join(root, 'contracts')));
}
