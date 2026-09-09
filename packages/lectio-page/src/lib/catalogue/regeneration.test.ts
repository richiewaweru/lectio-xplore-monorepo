import { execFileSync } from 'node:child_process';
import {
	copyFileSync,
	mkdirSync,
	mkdtempSync,
	readdirSync,
	readFileSync,
	rmSync,
	writeFileSync
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const packageRoot = process.cwd();
const contractsDir = join(packageRoot, 'contracts');
const scriptPath = join(packageRoot, 'scripts/export-contracts.ts');
const tsxBin = join(
	packageRoot,
	process.platform === 'win32' ? 'node_modules/tsx/dist/cli.mjs' : 'node_modules/.bin/tsx'
);

const CATALOGUE_FILES = [
	'lectio-document-v2.schema.json',
	'object-catalogue.v1.json',
	'intent-catalogue.v1.json'
] as const;

/** Runs the real exporter as a child process, not an in-process stand-in. */
function runExporter(sourceDir: string, outDir: string): void {
	const command = process.platform === 'win32' ? process.execPath : tsxBin;
	const args = [scriptPath, '--source-dir', sourceDir, '--out', outDir];
	execFileSync(command, process.platform === 'win32' ? [tsxBin, ...args] : args, {
		cwd: packageRoot,
		stdio: 'pipe'
	});
}

function seedSource(dir: string): void {
	mkdirSync(dir, { recursive: true });
	for (const name of CATALOGUE_FILES) {
		copyFileSync(join(contractsDir, name), join(dir, name));
	}
	copyTree(join(contractsDir, 'authoring'), join(dir, 'authoring'));
}

function copyTree(from: string, to: string): void {
	mkdirSync(to, { recursive: true });
	for (const entry of readdirSync(from, { withFileTypes: true })) {
		const source = join(from, entry.name);
		const target = join(to, entry.name);
		if (entry.isDirectory()) {
			copyTree(source, target);
		} else {
			copyFileSync(source, target);
		}
	}
}

function readJson<T>(path: string): T {
	return JSON.parse(readFileSync(path, 'utf8')) as T;
}

interface SelectionView {
	forms: Array<{ id: string; choose_when: string; capacity: Record<string, number> }>;
}
interface WriterView {
	forms: Record<
		string,
		{
			writer_guidance: Record<string, string>;
			instructions: { text: string; resource_ref: string };
			definition_hash: string;
		}
	>;
}
interface Manifest {
	generated_at: string;
	object_catalogue_version: string;
	files: Array<{ path: string; sha256: string; bytes: number }>;
}

describe('P01-K01 — the Print contract exporter regenerates reproducibly', () => {
	let baselineSource: string;
	let baselineOut: string;
	let mutatedSource: string;
	let mutatedOut: string;

	beforeAll(() => {
		const base = mkdtempSync(join(tmpdir(), 'lectio-page-base-'));
		const mutated = mkdtempSync(join(tmpdir(), 'lectio-page-mut-'));
		baselineSource = join(base, 'contracts');
		baselineOut = join(base, 'out');
		mutatedSource = join(mutated, 'contracts');
		mutatedOut = join(mutated, 'out');
		seedSource(baselineSource);
		seedSource(mutatedSource);
		runExporter(baselineSource, baselineOut);
	});

	afterAll(() => {
		rmSync(join(baselineSource, '..'), { recursive: true, force: true });
		rmSync(join(mutatedSource, '..'), { recursive: true, force: true });
	});

	it('reproduces byte-identical output apart from the timestamp', () => {
		const first = readJson<Manifest>(join(baselineOut, 'manifest.json'));
		const firstSelection = readFileSync(
			join(baselineOut, 'generated/form-selection-view.v1.json'),
			'utf8'
		);

		runExporter(baselineSource, baselineOut);
		const second = readJson<Manifest>(join(baselineOut, 'manifest.json'));

		expect(second.files).toEqual(first.files);
		expect(
			readFileSync(join(baselineOut, 'generated/form-selection-view.v1.json'), 'utf8')
		).toBe(firstSelection);
		expect(Date.parse(second.generated_at)).not.toBeNaN();
	});

	it('matches the generated copies committed to the package', () => {
		for (const name of [
			'generated/form-selection-view.v1.json',
			'generated/form-writer-view.v1.json',
			'generated/intent-object-map.v1.json'
		]) {
			expect(readFileSync(join(baselineOut, name), 'utf8'), name).toBe(
				readFileSync(join(contractsDir, name), 'utf8')
			);
		}
	});

	it('propagates a deliberate choose_when and capacity change into the selection view', () => {
		const catalogue = readJson<{
			catalogue_version: string;
			objects: Record<string, Record<string, unknown>>;
		}>(join(mutatedSource, 'object-catalogue.v1.json'));

		catalogue.objects.table = {
			...catalogue.objects.table,
			earns_its_place_when: 'P01-K01 mutated choose_when',
			capacity: { ...(catalogue.objects.table!.capacity as object), rowsMax: 12 }
		};
		writeFileSync(
			join(mutatedSource, 'object-catalogue.v1.json'),
			JSON.stringify(catalogue, null, 2) + '\n'
		);

		runExporter(mutatedSource, mutatedOut);

		const baseline = readJson<SelectionView>(
			join(baselineOut, 'generated/form-selection-view.v1.json')
		);
		const mutated = readJson<SelectionView>(
			join(mutatedOut, 'generated/form-selection-view.v1.json')
		);

		const baselineTable = baseline.forms.find((form) => form.id === 'table');
		const mutatedTable = mutated.forms.find((form) => form.id === 'table');

		expect(baselineTable?.choose_when).not.toBe('P01-K01 mutated choose_when');
		expect(baselineTable?.capacity.rowsMax).toBe(8);
		expect(mutatedTable?.choose_when).toBe('P01-K01 mutated choose_when');
		expect(mutatedTable?.capacity.rowsMax).toBe(12);

		const baselineHash = readJson<Manifest>(join(baselineOut, 'manifest.json')).files.find(
			(file) => file.path === 'generated/form-selection-view.v1.json'
		)?.sha256;
		const mutatedHash = readJson<Manifest>(join(mutatedOut, 'manifest.json')).files.find(
			(file) => file.path === 'generated/form-selection-view.v1.json'
		)?.sha256;
		expect(mutatedHash).not.toBe(baselineHash);
	});

	it('propagates a deliberate writer-guidance change into the writer view', () => {
		const catalogue = readJson<{
			objects: Record<string, Record<string, unknown>>;
		}>(join(mutatedSource, 'object-catalogue.v1.json'));

		catalogue.objects.aside = {
			...catalogue.objects.aside,
			writer_guidance: {
				...(catalogue.objects.aside!.writer_guidance as Record<string, string>),
				body: 'P01-K01 mutated field guidance'
			}
		};
		writeFileSync(
			join(mutatedSource, 'object-catalogue.v1.json'),
			JSON.stringify(catalogue, null, 2) + '\n'
		);

		runExporter(mutatedSource, mutatedOut);

		const baseline = readJson<WriterView>(join(baselineOut, 'generated/form-writer-view.v1.json'));
		const mutated = readJson<WriterView>(join(mutatedOut, 'generated/form-writer-view.v1.json'));

		expect(baseline.forms.aside!.writer_guidance.body).not.toBe(
			'P01-K01 mutated field guidance'
		);
		expect(mutated.forms.aside!.writer_guidance.body).toBe('P01-K01 mutated field guidance');
	});

	it('propagates a package instruction change into the writer view and definition hash', () => {
		const instructionPath = join(mutatedSource, 'authoring/instructions/prose-writer-v1.txt');
		writeFileSync(
			instructionPath,
			`${readFileSync(instructionPath, 'utf8')}\n\nP01-A01 instruction marker.\n`,
			'utf8'
		);

		runExporter(mutatedSource, mutatedOut);

		const baseline = readJson<WriterView>(join(baselineOut, 'generated/form-writer-view.v1.json'));
		const mutated = readJson<WriterView>(join(mutatedOut, 'generated/form-writer-view.v1.json'));

		expect(mutated.forms.prose!.instructions.text).toContain('P01-A01 instruction marker.');
		expect(mutated.forms.prose!.definition_hash).not.toBe(
			baseline.forms.prose!.definition_hash
		);
	});

	it('drops a form from the selection view when the source marks it unselectable', () => {
		const catalogue = readJson<{
			objects: Record<string, Record<string, unknown>>;
		}>(join(mutatedSource, 'object-catalogue.v1.json'));

		catalogue.objects.figure = {
			...catalogue.objects.figure,
			form_selectable: false,
			not_form_selectable_because: 'P01-K01 mutated exclusion'
		};
		writeFileSync(
			join(mutatedSource, 'object-catalogue.v1.json'),
			JSON.stringify(catalogue, null, 2) + '\n'
		);

		runExporter(mutatedSource, mutatedOut);

		const mutated = readJson<
			SelectionView & { excluded_forms: Array<{ id: string; reason: string }> }
		>(join(mutatedOut, 'generated/form-selection-view.v1.json'));

		expect(mutated.forms.map((form) => form.id)).not.toContain('figure');
		expect(mutated.excluded_forms).toContainEqual({
			id: 'figure',
			reason: 'P01-K01 mutated exclusion'
		});
	});
});
