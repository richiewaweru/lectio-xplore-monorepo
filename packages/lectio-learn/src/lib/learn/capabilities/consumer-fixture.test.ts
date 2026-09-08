// @vitest-environment node

/**
 * Package-only consumer fixture.
 *
 * This test stands in for a real consumer: it imports the published capability
 * surface and nothing else — no deep paths into component folders, no registry,
 * no renderer. If a consumer needs an internal import to select and evaluate a
 * capability, the package surface is incomplete and this test is where that
 * shows up.
 *
 * It then plays the whole consumer sequence — read selection view, choose a
 * capability, fetch its writer contract, author a payload, evaluate a response
 * through the runtime view's evaluator — using only that surface.
 */

import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

// One import site, and it is the published capability entry point. Anything the
// fixture cannot get from here is missing from the package surface.
import {
	buildRuntimeView,
	buildSelectionView,
	buildTeachingView,
	buildWriterView,
	evaluateInteraction,
	isSelectable,
	learnCapabilities,
	quizContentToInteractionContract,
	validateCapabilityRecords,
	type LearnCapabilityRecord,
	type LearnInteractionContract
} from './index';

const catalogue: readonly LearnCapabilityRecord[] = learnCapabilities;

describe('package-only consumer', () => {
	it('can validate the catalogue it was given', () => {
		expect(validateCapabilityRecords(catalogue)).toEqual([]);
	});

	it('sees no incomplete or unavailable capability in the generation-ready view', () => {
		const selection = buildSelectionView([...catalogue]);
		const offered = selection.capabilities.map((entry) => entry.id);

		const notReady = catalogue.filter((record) => !isSelectable(record));
		expect(notReady.length, 'the fixture is only meaningful if something is held back').toBeGreaterThan(
			0
		);
		for (const record of notReady) {
			expect(offered, `${record.id} (${record.readiness}/${record.availability})`).not.toContain(
				record.id
			);
		}

		// Incomplete / unavailable / unwired interactions stay out of the generation-ready view.
		// Sequence is offered after P06 Builder + selection wiring.
		for (const record of catalogue.filter((entry) => entry.kind === 'interaction')) {
			if (record.id === 'sequence') {
				expect(offered, record.id).toContain(record.id);
				continue;
			}
			expect(offered, record.id).not.toContain(record.id);
		}
	});

	it('can plan in shared vocabulary without learning a single native id', () => {
		const teaching = buildTeachingView([...catalogue]);
		const nativeIds = new Set(catalogue.map((record) => record.id));
		const serialized = JSON.stringify(teaching);
		for (const id of nativeIds) {
			// Hyphenated capability ids never occur in natural prose, so a hit is a leak.
			if (!id.includes('-')) continue;
			expect(serialized.includes(id), `teaching view leaks "${id}"`).toBe(false);
		}
		expect(teaching.coverage.some((entry) => entry.supported_today)).toBe(true);
	});

	it('can go from selection to a scored response using only the public surface', () => {
		const selection = buildSelectionView([...catalogue]);
		const chosen = selection.capabilities.find((entry) => entry.id === 'quiz-check');
		expect(chosen, 'quiz-check should be selectable').toBeDefined();
		expect(chosen!.evaluation_mode).toBe('auto-score');

		// The selection step must not have handed the consumer an answer key.
		expect(JSON.stringify(chosen)).not.toMatch(/correct|answer/i);

		const writer = buildWriterView([...catalogue]).capabilities[chosen!.id];
		expect(writer?.payload_schema_ref).toBeTruthy();
		expect(Object.keys(writer!.field_guidance).length).toBeGreaterThan(0);

		const runtime = buildRuntimeView([...catalogue]).capabilities[chosen!.id];
		expect(runtime?.evaluation.contract_ref).toMatch(/quizContentToInteractionContract/);

		// Author a payload against the writer contract and score it through the
		// adapter the runtime view named.
		const contract: LearnInteractionContract = quizContentToInteractionContract(
			{
				question: 'Where does the mass of a plant come from?',
				options: [
					{ text: 'From the soil', correct: false },
					{ text: 'From carbon dioxide in the air', correct: true },
					{ text: 'From sunlight alone', correct: false }
				],
				feedback_correct: 'Yes.',
				feedback_incorrect: 'Not yet.'
			},
			'sec-1-quiz'
		);

		const correctId = (
			contract.config as { options: Array<{ id: string }>; correct_option_id: string }
		).correct_option_id;
		expect(evaluateInteraction(contract, { selected_option_id: correctId })).toMatchObject({
			outcome: 'correct',
			score_earned: 1
		});
	});

	it('reaches nothing renderer-bound: no .svelte anywhere in the entry import graph', () => {
		const here = dirname(fileURLToPath(import.meta.url));
		const srcLib = resolve(here, '../..');
		const seen = new Set<string>();
		const svelteImports: string[] = [];

		const resolveSpecifier = (from: string, specifier: string): string | null => {
			const base = specifier.startsWith('$lib/')
				? join(srcLib, specifier.slice('$lib/'.length))
				: specifier.startsWith('.')
					? resolve(dirname(from), specifier)
					: null;
			if (base === null) return null;
			for (const candidate of [base, `${base}.ts`, join(base, 'index.ts')]) {
				try {
					readFileSync(candidate, 'utf8');
					return candidate;
				} catch {
					continue;
				}
			}
			return base.endsWith('.svelte') ? base : null;
		};

		const walk = (file: string): void => {
			if (seen.has(file)) return;
			seen.add(file);
			const source = readFileSync(file, 'utf8');
			for (const match of source.matchAll(/from\s+'([^']+)'/g)) {
				const specifier = match[1]!;
				if (specifier.endsWith('.svelte')) {
					svelteImports.push(`${file} -> ${specifier}`);
					continue;
				}
				const target = resolveSpecifier(file, specifier);
				if (target && target.endsWith('.ts')) walk(target);
			}
		};

		walk(join(here, 'index.ts'));
		expect(svelteImports, 'the capability entry point pulls in a renderer').toEqual([]);
		expect(seen.size, 'the walk resolved nothing, so it proves nothing').toBeGreaterThan(3);
	});

	it('finds the capability entry point in the published exports map', () => {
		const pkg = JSON.parse(
			readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), '../../../../package.json'), 'utf8')
		) as { exports: Record<string, unknown> };
		expect(pkg.exports['./capabilities']).toMatchObject({
			default: './dist/learn/capabilities/index.js'
		});
	});

	it('is told why a held-back capability is held back, and what would unblock it', () => {
		const selection = buildSelectionView([...catalogue]);
		for (const entry of selection.excluded) {
			expect(entry.blocking_reasons.length, entry.id).toBeGreaterThan(0);
			expect(entry.path_to_readiness.length, entry.id).toBeGreaterThan(0);
			for (const reason of [...entry.blocking_reasons, ...entry.path_to_readiness]) {
				expect(reason.length, `${entry.id}: empty reason`).toBeGreaterThan(10);
			}
		}
	});
});
