import { execFileSync } from 'node:child_process';
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import type { TeachingView } from '../src/teaching-view';
import {
	projectIntentVocabulary,
	type IntentVocabularyFile,
	type SourceIntentCatalogue
} from '../scripts/export-contracts';

const packageRoot = join(import.meta.dirname, '..');
const scriptPath = join(packageRoot, 'scripts/export-contracts.ts');
const tsxBin = join(
	packageRoot,
	process.platform === 'win32' ? 'node_modules/tsx/dist/cli.mjs' : 'node_modules/.bin/tsx'
);

/** Runs the real exporter as a child process. */
function runExporter(vocabRoot: string, outRoot: string): void {
	const command = process.platform === 'win32' ? process.execPath : tsxBin;
	const args =
		process.platform === 'win32'
			? [tsxBin, scriptPath, '--vocab', vocabRoot, '--out', outRoot]
			: [scriptPath, '--vocab', vocabRoot, '--out', outRoot];
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
		cpSync(join(packageRoot, 'data'), join(baseline, 'data'), { recursive: true });
		cpSync(join(packageRoot, 'data'), join(mutated, 'data'), { recursive: true });
	});

	afterAll(() => {
		rmSync(baseline, { recursive: true, force: true });
		rmSync(mutated, { recursive: true, force: true });
	});

	it('reproduces byte-identical output apart from the timestamp', () => {
		runExporter(baseline, baseline);
		const firstManifest = readManifest(baseline);
		const firstView = readFileSync(join(baseline, 'generated/teaching-view.v1.json'), 'utf8');

		runExporter(baseline, baseline);
		const secondManifest = readManifest(baseline);
		const secondView = readFileSync(join(baseline, 'generated/teaching-view.v1.json'), 'utf8');

		expect(secondView).toBe(firstView);
		expect(secondManifest.files).toEqual(firstManifest.files);
		expect(Date.parse(secondManifest.generated_at)).not.toBeNaN();
	});

	it('matches the teaching view committed to the package', () => {
		expect(readFileSync(join(baseline, 'generated/teaching-view.v1.json'), 'utf8')).toBe(
			readFileSync(join(packageRoot, 'generated/teaching-view.v1.json'), 'utf8')
		);
		expect(readFileSync(join(baseline, 'data/instructional-intents.v1.json'), 'utf8')).toBe(
			readFileSync(join(packageRoot, 'data/instructional-intents.v1.json'), 'utf8')
		);
	});

	it('propagates a deliberate authored-intent change into the teaching view', () => {
		const vocabulary = JSON.parse(
			readFileSync(join(mutated, 'data/instructional-intents.v1.json'), 'utf8')
		) as IntentVocabularyFile;
		const before = vocabulary.intents['compare'];
		expect(before).toBeDefined();

		vocabulary.intents['compare'] = {
			...before!,
			label: 'P01-K01 mutated label',
			cognitive_job: 'P01-K01 mutated cognitive job'
		};
		writeFileSync(
			join(mutated, 'data/instructional-intents.v1.json'),
			JSON.stringify(vocabulary, null, '\t') + '\n'
		);

		runExporter(mutated, mutated);

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

	it('marks an intent unselectable when the authored vocabulary says so', () => {
		const catalogue = JSON.parse(
			readFileSync(join(packageRoot, '../lectio-page/contracts/intent-catalogue.v1.json'), 'utf8')
		) as SourceIntentCatalogue;
		catalogue.intents['reflect'] = { ...catalogue.intents['reflect']!, selectable: false };
		const vocabulary = projectIntentVocabulary(catalogue);

		expect(Object.keys(vocabulary.intents)).toHaveLength(32);
		expect(vocabulary.intents['reflect']?.teaching_selectable).toBe(false);
		expect(vocabulary.source.package).toBe('@lectio/contracts');
	});
});
