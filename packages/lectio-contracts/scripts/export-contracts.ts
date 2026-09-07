/**
 * scripts/export-contracts.ts
 *
 * Two jobs, in order:
 *
 * 1. Project `data/instructional-intents.v1.json` from the canonical Print intent
 *    catalogue. Identifiers, labels, roles, cognitive jobs and neighbouring
 *    boundaries are copied verbatim; `valid_objects` and generation guidance are
 *    dropped because they are native inventory, not shared vocabulary.
 * 2. Regenerate `generated/teaching-view.v1.json` and `generated/manifest.json`.
 *
 *   pnpm --filter @lectio/contracts export-contracts
 *   tsx scripts/export-contracts.ts --source <intent-catalogue.json> --out <dir>
 *
 * `--source` and `--out` exist so the regeneration gate can drive the real
 * exporter against a mutated source copy without touching the committed files.
 * `generated_at` is the only non-reproducible field in the output.
 */

import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import learnerActions from '../data/learner-actions.v1.json';
import { projectTeachingView } from '../src/teaching-view';
import type { InstructionalIntentRecord } from '../src/intents';
import type { LearnerActionRecord } from '../src/actions';

export const INTENT_VOCABULARY_VERSION = '1.0.0';

export interface SourceIntent {
	teacher_label: string;
	pedagogical_role: string;
	cognitive_job: string;
	valid_objects: string[];
	generation_guidance: string;
	choose_when?: string;
	not_when?: Record<string, string>;
	selectable?: boolean;
}

export interface SourceIntentCatalogue {
	catalogue_version: string;
	intents: Record<string, SourceIntent>;
}

export interface IntentVocabularyFile {
	vocabulary_version: string;
	note: string;
	source: { package: string; file: string; catalogue_version: string };
	intents: Record<string, InstructionalIntentRecord>;
}

/** Pure projection: canonical Print intent catalogue → neutral shared vocabulary. */
export function projectIntentVocabulary(
	catalogue: SourceIntentCatalogue
): IntentVocabularyFile {
	const intents: Record<string, InstructionalIntentRecord> = {};
	for (const [id, record] of Object.entries(catalogue.intents)) {
		intents[id] = {
			label: record.teacher_label,
			pedagogical_role: record.pedagogical_role,
			cognitive_job: record.cognitive_job,
			choose_when: record.choose_when ?? null,
			boundaries: record.not_when ?? {},
			teaching_selectable: record.selectable !== false
		};
	}
	return {
		vocabulary_version: INTENT_VOCABULARY_VERSION,
		note: 'Canonical instructional intent identifiers. Projected from the Print intent catalogue by scripts/export-contracts.ts — edit the source catalogue, never this file. Native inventory (valid_objects, generation guidance) is deliberately dropped.',
		source: {
			package: '@lectio/page',
			file: 'contracts/intent-catalogue.v1.json',
			catalogue_version: catalogue.catalogue_version
		},
		intents
	};
}

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), '..');

function argValue(flag: string): string | null {
	const index = process.argv.indexOf(flag);
	if (index === -1) return null;
	return process.argv[index + 1] ?? null;
}

export function exportContracts(sourcePath: string, outRoot: string): void {
	const catalogue = JSON.parse(readFileSync(sourcePath, 'utf8')) as SourceIntentCatalogue;
	const vocabulary = projectIntentVocabulary(catalogue);

	const dataDir = join(outRoot, 'data');
	const generatedDir = join(outRoot, 'generated');
	mkdirSync(dataDir, { recursive: true });
	mkdirSync(generatedDir, { recursive: true });

	writeFileSync(
		join(dataDir, 'instructional-intents.v1.json'),
		JSON.stringify(vocabulary, null, '\t') + '\n'
	);

	const teachingView = projectTeachingView({
		intents: vocabulary.intents,
		actions: learnerActions.actions as unknown as Record<string, LearnerActionRecord>,
		intent_vocabulary_version: vocabulary.vocabulary_version,
		action_vocabulary_version: learnerActions.vocabulary_version
	});
	writeFileSync(
		join(generatedDir, 'teaching-view.v1.json'),
		JSON.stringify(teachingView, null, '\t') + '\n'
	);

	// `learner-actions.v1.json` is authored, not generated: it is hashed from the
	// package where it lives and never rewritten by the exporter.
	const hashed: Array<{ path: string; from: string }> = [
		{ path: 'data/instructional-intents.v1.json', from: outRoot },
		{ path: 'data/learner-actions.v1.json', from: packageRoot },
		{ path: 'generated/teaching-view.v1.json', from: outRoot }
	];

	const files = hashed.map(({ path, from }) => {
		const bytes = readFileSync(join(from, path));
		return {
			path,
			sha256: createHash('sha256').update(bytes).digest('hex'),
			bytes: bytes.byteLength
		};
	});

	writeFileSync(
		join(generatedDir, 'manifest.json'),
		JSON.stringify(
			{
				manifest_version: '1.0.0',
				package: '@lectio/contracts',
				intent_vocabulary_version: vocabulary.vocabulary_version,
				action_vocabulary_version: learnerActions.vocabulary_version,
				teaching_view_version: teachingView.view_version,
				intent_source_catalogue_version: catalogue.catalogue_version,
				generated_at: new Date().toISOString(),
				files
			},
			null,
			'\t'
		) + '\n'
	);

	console.log(`Synced instructional vocabulary from ${sourcePath}`);
	console.log(
		`  ${Object.keys(vocabulary.intents).length} intents (${teachingView.intents.length} teaching-selectable)`
	);
	console.log(`  ${teachingView.learner_actions.length} learner actions`);
	for (const file of files) {
		console.log(`  ${file.path}  ${file.sha256.slice(0, 12)}…  ${file.bytes}b`);
	}
}

const invokedDirectly =
	process.argv[1] !== undefined &&
	resolve(process.argv[1]) === fileURLToPath(import.meta.url);

if (invokedDirectly) {
	const source = resolve(
		argValue('--source') ??
			join(packageRoot, '../lectio-page/contracts/intent-catalogue.v1.json')
	);
	exportContracts(source, resolve(argValue('--out') ?? packageRoot));
}
