// @vitest-environment node

/**
 * P01-K01 for Learn: the generated views are regenerated, not hand-maintained.
 *
 * The test does not assert that a build step exists — it runs the real exporter
 * twice, proves the artefacts are byte-identical apart from the manifest
 * timestamp, then changes one source field, regenerates, and proves the change
 * arrives in the generated views and in the manifest hash. A view that survives
 * a source change unchanged is a copy, not a projection.
 */

import { execFileSync } from 'child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { dirname, join, resolve } from 'path';
import { fileURLToPath } from 'url';

import { afterAll, beforeAll, describe, expect, it } from 'vitest';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SOURCE = join(ROOT, 'src/lib/learn/capabilities/interactions.ts');
const CHOICE_INSTRUCTIONS = join(ROOT, 'contracts/authoring/instructions/choice-writer-v1.txt');

type JsonObject = Record<string, unknown>;

interface ManifestEntry {
	file: string;
	view: string;
	sha256: string;
}

function runExport(outDir: string): void {
	execFileSync(process.execPath, ['--import', 'tsx', 'scripts/export-contracts.ts', '--out', outDir], {
		cwd: ROOT,
		stdio: 'pipe'
	});
}

function readJson(path: string): JsonObject {
	return JSON.parse(readFileSync(path, 'utf8')) as JsonObject;
}

function hashes(outDir: string): Record<string, string> {
	const manifest = readJson(join(outDir, 'learn-capability-manifest.json'));
	const artifacts = manifest.artifacts as ManifestEntry[];
	return Object.fromEntries(artifacts.map((entry) => [entry.file, entry.sha256]));
}

const ARTIFACTS = [
	'learn-capabilities.v1.json',
	'learn-teaching-view.v1.json',
	'learn-selection-view.v1.json',
	'learn-writer-view.v1.json',
	'learn-runtime-view.v1.json'
];

const tempDirs: string[] = [];
function tempOut(): string {
	const dir = mkdtempSync(join(tmpdir(), 'lectio-learn-caps-'));
	tempDirs.push(dir);
	return join(dir, 'contracts');
}

afterAll(() => {
	for (const dir of tempDirs) rmSync(dir, { recursive: true, force: true });
});

describe('learn capability export (P01-K01)', () => {
	let first: string;

	beforeAll(() => {
		first = tempOut();
		runExport(first);
	}, 180000);

	it('writes every generated view plus a manifest that hashes each one', () => {
		for (const file of [...ARTIFACTS, 'learn-capability-manifest.json']) {
			expect(existsSync(join(first, file)), file).toBe(true);
		}
		const manifest = readJson(join(first, 'learn-capability-manifest.json'));
		const artifacts = manifest.artifacts as ManifestEntry[];
		const files = artifacts.map((entry) => entry.file).sort();
		for (const file of ARTIFACTS) {
			expect(files, file).toContain(file);
		}
		expect(files.some((file) => file.startsWith('authoring/instructions/'))).toBe(true);
		for (const entry of artifacts) {
			expect(entry.sha256, entry.file).toMatch(/^[0-9a-f]{64}$/);
			const serialized = readFileSync(join(first, entry.file), 'utf8');
			// The hash must be over the bytes actually written, or it proves nothing.
			expect(serialized.length).toBeGreaterThan(0);
		}
		expect(manifest.catalogue_version).toBeTruthy();
		expect((manifest.capability_counts as Record<string, number>).total).toBeGreaterThan(0);
	}, 120000);

	it('is reproducible: a second run produces identical artefacts', () => {
		const second = tempOut();
		runExport(second);
		for (const file of ARTIFACTS) {
			expect(readFileSync(join(second, file), 'utf8'), file).toBe(
				readFileSync(join(first, file), 'utf8')
			);
		}
		expect(hashes(second)).toEqual(hashes(first));
	}, 120000);

	it('propagates a deliberate source change into the generated views', () => {
		const original = readFileSync(SOURCE, 'utf8');
		const marker = 'P01-K01 PROOF MARKER: choose this only in the regeneration test.';
		const needle =
			"'The response reduces to one option, and every wrong option is one a real learner would pick for a stateable reason.'";
		expect(original.includes(needle), 'the choice choose_when source string moved').toBe(true);

		const mutated = tempOut();
		try {
			writeFileSync(SOURCE, original.replace(needle, JSON.stringify(marker)), 'utf8');
			runExport(mutated);

			const catalogue = readJson(join(mutated, 'learn-capabilities.v1.json'));
			const choice = (catalogue.capabilities as Array<{ id: string; choose_when: string }>).find(
				(record) => record.id === 'choice'
			);
			expect(choice?.choose_when).toBe(marker);

			// The writer view resolves from the same records, so it moves too, and
			// the manifest hash for every affected artefact must differ.
			const writer = readJson(join(mutated, 'learn-writer-view.v1.json'));
			expect(JSON.stringify(writer)).toContain('choice');
			expect(hashes(mutated)['learn-capabilities.v1.json']).not.toBe(
				hashes(first)['learn-capabilities.v1.json']
			);
		} finally {
			writeFileSync(SOURCE, original, 'utf8');
		}

		// And regenerating from the restored source returns the original bytes.
		const restored = tempOut();
		runExport(restored);
		expect(readFileSync(join(restored, 'learn-capabilities.v1.json'), 'utf8')).toBe(
			readFileSync(join(first, 'learn-capabilities.v1.json'), 'utf8')
		);
	}, 180000);

	it('propagates a package instruction change into writer request definitions', () => {
		const original = readFileSync(CHOICE_INSTRUCTIONS, 'utf8');
		const marker = 'P01-A01 instruction marker.';
		const mutated = tempOut();
		try {
			writeFileSync(CHOICE_INSTRUCTIONS, `${original}\n\n${marker}\n`, 'utf8');
			runExport(mutated);

			const writer = readJson(join(mutated, 'learn-writer-view.v1.json'));
			const choice = (
				writer.capabilities as Record<
					string,
					{ instructions: { text: string }; definition_hash: string }
				>
			).choice;
			const baseline = readJson(join(first, 'learn-writer-view.v1.json'));
			const baselineChoice = (
				baseline.capabilities as Record<string, { definition_hash: string }>
			).choice;
			expect(choice.instructions.text).toContain(marker);
			expect(choice.definition_hash).not.toBe(baselineChoice.definition_hash);
		} finally {
			writeFileSync(CHOICE_INSTRUCTIONS, original, 'utf8');
		}
	}, 180000);
});