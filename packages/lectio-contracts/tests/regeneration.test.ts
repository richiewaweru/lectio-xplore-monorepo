import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import type { TeachingView } from '../src/teaching-view';
import {
	projectIntentVocabulary,
	type SourceIntentCatalogue
} from '../scripts/export-contracts';

const packageRoot = join(import.meta.dirname, '..');
const canonicalSource = join(
	packageRoot,
	'../lectio-page/contracts/intent-catalogue.v1.json'
);
const scriptPath = join(packageRoot, 'scripts/export-contracts.ts');
const tsxBin = join(
	packageRoot,
	process.platform === 'win32' ? 'node_modules/tsx/dist/cli.mjs' : 'node_modules/.bin/tsx'
);

/** Runs the real exporter as a child process, not an in-process re-implementation. */
function runExporter(sourcePath: string, outRoot: string): void {
	const command = process.platform === 'win32' ? process.execPath : tsxBin;
	const args =
		process.platform === 'win32'
			? [tsxBin, scriptPath, '--source', sourcePath, '--out', outRoot]
			: [scriptPath, '--source', sourcePath, '--out', outRoot];
	execFileSync(command, args, { cwd: packageRoot, stdio: 'pipe' });
}

function readView(outRoot: string): TeachingView {
	return JSON.parse(
		readFileSync(join(outRoot, 'generated/teaching-view.v1.json'), 'utf8')
	) as TeachingView;
}

function readManifest(outRoot: string): {
	generated_at: string;
	files: Array<{ path: string; sha256: string; bytes: number }>;
} {
	return JSON.parse(readFileSync(join(outRoot, 'generated/manifest.json'), 'utf8'));
}

describe('P01-K01 — the shared vocabulary exporter regenerates reproducibly', () => {
	let baseline: string;
	let mutated: string;

	beforeAll(() => {
		baseline = mkdtempSync(join(tmpdir(), 'lectio-contracts-base-'));
		mutated = mkdtempSync(join(tmpdir(), 'lectio-contracts-mut-'));
	});

	afterAll(() => {
		rmSync(baseline, { recursive: true, force: true });
		rmSync(mutated, { recursive: true, force: true });
	});

	it('reproduces byte-identical output apart from the timestamp', () => {
		runExporter(canonicalSource, baseline);
		const firstManifest = readManifest(baseline);
		const firstView = readFileSync(join(baseline, 'generated/teaching-view.v1.json'), 'utf8');

		runExporter(canonicalSource, baseline);
		const secondManifest = readManifest(baseline);
		const secondView = readFileSync(join(baseline, 'generated/teaching-view.v1.json'), 'utf8');

		expect(secondView).toBe(firstView);
		expect(secondManifest.files).toEqual(firstManifest.files);
		expect(Date.parse(secondManifest.generated_at)).not.toBeNaN();
	});

	it('matches the copies committed to the package', () => {
		expect(readFileSync(join(baseline, 'generated/teaching-view.v1.json'), 'utf8')).toBe(
			readFileSync(join(packageRoot, 'generated/teaching-view.v1.json'), 'utf8')
		);
		expect(readFileSync(join(baseline, 'data/instructional-intents.v1.json'), 'utf8')).toBe(
			readFileSync(join(packageRoot, 'data/instructional-intents.v1.json'), 'utf8')
		);
	});

	it('propagates a deliberate source-field change into the generated teaching view', () => {
		const catalogue = JSON.parse(
			readFileSync(canonicalSource, 'utf8')
		) as SourceIntentCatalogue;
		const before = catalogue.intents['compare'];
		expect(before).toBeDefined();

		catalogue.intents['compare'] = {
			...before!,
			teacher_label: 'P01-K01 mutated label',
			cognitive_job: 'P01-K01 mutated cognitive job'
		};
		const mutatedSource = join(mutated, 'intent-catalogue.mutated.json');
		writeFileSync(mutatedSource, JSON.stringify(catalogue, null, 2));

		runExporter(mutatedSource, mutated);

		const baselineCompare = readView(baseline).intents.find((i) => i.id === 'compare');
		const mutatedCompare = readView(mutated).intents.find((i) => i.id === 'compare');

		expect(baselineCompare?.label).toBe('Compare');
		expect(mutatedCompare?.label).toBe('P01-K01 mutated label');
		expect(mutatedCompare?.cognitive_job).toBe('P01-K01 mutated cognitive job');

		const baselineHash = readManifest(baseline).files.find(
			(f) => f.path === 'generated/teaching-view.v1.json'
		)?.sha256;
		const mutatedHash = readManifest(mutated).files.find(
			(f) => f.path === 'generated/teaching-view.v1.json'
		)?.sha256;
		expect(mutatedHash).not.toBe(baselineHash);
	});

	it('drops a source intent from the view when the source marks it unselectable', () => {
		const catalogue = JSON.parse(
			readFileSync(canonicalSource, 'utf8')
		) as SourceIntentCatalogue;
		catalogue.intents['reflect'] = { ...catalogue.intents['reflect']!, selectable: false };
		const vocabulary = projectIntentVocabulary(catalogue);

		expect(Object.keys(vocabulary.intents)).toHaveLength(32);
		expect(vocabulary.intents['reflect']?.teaching_selectable).toBe(false);
	});
});
