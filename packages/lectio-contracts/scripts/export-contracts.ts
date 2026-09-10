/**
 * scripts/export-contracts.ts
 *
 * Regenerates teaching-view + manifest from the authored shared vocabulary:
 *   - data/instructional-intents.v1.json  (canonical intent owner: @lectio/contracts)
 *   - data/learner-actions.v1.json        (authored here)
 *
 * Print (`@lectio/page`) adapts these intent ids with valid_objects / generation
 * guidance. Do not project intents from the page catalogue anymore.
 *
 *   pnpm --filter @lectio/contracts export-contracts
 *   tsx scripts/export-contracts.ts --out <dir>
 *
 * `--out` exists so the regeneration gate can drive the exporter against a
 * temporary package copy without touching the committed files.
 * `generated_at` is the only non-reproducible field in the output.
 */

import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import learnerActions from '../data/learner-actions.v1.json';
import { projectTeachingView } from '../src/teaching-view';
import type { InstructionalIntentRecord } from '../src/intents';
import type { LearnerActionRecord } from '../src/actions';

export const INTENT_VOCABULARY_VERSION = '1.0.0';

/** Legacy Print catalogue shape — kept only for one-shot migration helpers/tests. */
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

/**
 * Convert a Print intent catalogue into neutral shared vocabulary.
 * Prefer editing `data/instructional-intents.v1.json` directly; this helper
 * remains for alignment checks and historical migration.
 */
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
		note: 'Canonical instructional intent identifiers. Owned by @lectio/contracts. Print adapts these ids with valid_objects and generation guidance.',
		source: {
			package: '@lectio/contracts',
			file: 'data/instructional-intents.v1.json',
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

function loadAuthoredVocabulary(root: string): IntentVocabularyFile {
	const path = join(root, 'data/instructional-intents.v1.json');
	return JSON.parse(readFileSync(path, 'utf8')) as IntentVocabularyFile;
}

function loadLearnerActions(root: string): typeof learnerActions {
	const path = join(root, 'data/learner-actions.v1.json');
	return JSON.parse(readFileSync(path, 'utf8')) as typeof learnerActions;
}

/** Regenerate teaching-view + manifest from authored contracts vocabulary. */
export function exportContracts(outRoot: string, vocabularyRoot: string = packageRoot): void {
	const vocabulary = loadAuthoredVocabulary(vocabularyRoot);
	const actionsFile = loadLearnerActions(vocabularyRoot);

	const dataDir = join(outRoot, 'data');
	const generatedDir = join(outRoot, 'generated');
	mkdirSync(dataDir, { recursive: true });
	mkdirSync(generatedDir, { recursive: true });

	// Authored intents are copied, never rewritten from Print.
	writeFileSync(
		join(dataDir, 'instructional-intents.v1.json'),
		JSON.stringify(vocabulary, null, '\t') + '\n'
	);
	copyFileSync(
		join(vocabularyRoot, 'data/learner-actions.v1.json'),
		join(dataDir, 'learner-actions.v1.json')
	);

	const teachingView = projectTeachingView({
		intents: vocabulary.intents,
		actions: actionsFile.actions as unknown as Record<string, LearnerActionRecord>,
		intent_vocabulary_version: vocabulary.vocabulary_version,
		action_vocabulary_version: actionsFile.vocabulary_version
	});
	writeFileSync(
		join(generatedDir, 'teaching-view.v1.json'),
		JSON.stringify(teachingView, null, '\t') + '\n'
	);

	const hashed: Array<{ path: string; from: string }> = [
		{ path: 'data/instructional-intents.v1.json', from: outRoot },
		{ path: 'data/learner-actions.v1.json', from: outRoot },
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
				action_vocabulary_version: actionsFile.vocabulary_version,
				teaching_view_version: teachingView.view_version,
				intent_source_catalogue_version: vocabulary.source.catalogue_version,
				generated_at: new Date().toISOString(),
				files
			},
			null,
			'\t'
		) + '\n'
	);

	console.log(`Synced teaching view from authored @lectio/contracts vocabulary`);
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
	const outRoot = resolve(argValue('--out') ?? packageRoot);
	const vocabRoot = resolve(argValue('--vocab') ?? packageRoot);
	exportContracts(outRoot, vocabRoot);
}
