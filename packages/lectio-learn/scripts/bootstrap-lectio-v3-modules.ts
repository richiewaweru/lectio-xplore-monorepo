/**
 * Bootstraps `src/lib/lectio/components/<id>/` from the legacy registry.
 *
 *   pnpm tsx scripts/bootstrap-lectio-v3-modules.ts
 */
import { mkdirSync, unlinkSync, writeFileSync } from 'fs';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

import type { LectioCapabilities } from '../src/lib/lectio/core/types';
import { legacyBootstrapRegistry as legacyRegistry } from './legacy-registry-for-bootstrap';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const COMPONENTS = resolve(ROOT, 'src/lib/lectio/components');
const REGISTRY_DIR = resolve(ROOT, 'src/lib/lectio/registry');

function capsFor(id: string): LectioCapabilities {
	const practicePack = ['practice-stack', 'quiz-check', 'short-answer', 'fill-in-blank'].includes(id);
	const reflectionPack = ['reflection-prompt', 'student-textbox'].includes(id);
	const mediaIds = [
		'diagram-block',
		'diagram-compare',
		'diagram-series',
		'image-block',
		'video-embed',
		'timeline-block'
	].includes(id);

	if (practicePack)
		return {
			acceptsMedia: true,
			acceptsQuestions: true,
			producesAnswerKey: true,
			interactive: false,
			isMedia: false
		};
	if (reflectionPack)
		return {
			acceptsMedia: false,
			acceptsQuestions: true,
			producesAnswerKey: false,
			interactive: false,
			isMedia: false
		};
	if (mediaIds)
		return {
			acceptsMedia: false,
			acceptsQuestions: false,
			producesAnswerKey: false,
			interactive: false,
			isMedia: true
		};
	if (id === 'simulation-block')
		return {
			acceptsMedia: false,
			acceptsQuestions: false,
			producesAnswerKey: false,
			interactive: true,
			isMedia: true
		};

	return {
		acceptsMedia: false,
		acceptsQuestions: false,
		producesAnswerKey: false,
		interactive: false,
		isMedia: false
	};
}

function printFor(id: string, fallback: string) {
	const itemized: Record<string, string> = {
		'definition-family': '.definition-family-print-item',
		'diagram-series': '.diagram-series-print-item',
		'worked-example-card': '.worked-step-print',
		'process-steps': '.process-print-step',
		'practice-stack': '.practice-print-problem',
		'timeline-block': '.timeline-print-event'
	};

	const prose = new Set([
		'explanation-block',
		'hook-hero',
		'summary-block',
		'glossary-inline',
		'glossary-rail',
		'what-next-bridge'
	]);
	const table = new Set(['comparison-grid', 'insight-strip']);
	const colorReset = new Set(['hook-hero', 'summary-block', 'glossary-rail', 'insight-strip']);

	let breakBehavior: 'atomic' | 'itemized' | 'table' | 'prose' = 'atomic';
	if (itemized[id]) breakBehavior = 'itemized';
	else if (table.has(id)) breakBehavior = 'table';
	else if (prose.has(id)) breakBehavior = 'prose';

	const hasMedia = ['diagram-block', 'diagram-compare', 'diagram-series', 'image-block'].includes(id);
	const mediaConstraint =
		id === 'diagram-series'
			? ('constrain-height' as const)
			: hasMedia
				? ('constrain-width' as const)
				: undefined;

	const base = {
		breakBehavior,
		preferredWidth: 'full' as const,
		hasMedia,
		...(mediaConstraint ? { mediaConstraint } : {}),
		requiresColorReset: colorReset.has(id),
		fallback
	};

	if (breakBehavior === 'itemized') {
		return { ...base, itemSelector: itemized[id] };
	}

	if (id === 'glossary-inline') {
		return { ...base, preferredWidth: 'content-fit' as const };
	}

	return base;
}

const EXAMPLES: Record<string, unknown[]> = {
	'section-header': [{ title: 'Intro', subject: 'Mathematics', grade_band: 'secondary' }],
	'hook-hero': [{ headline: 'Why?', body: 'Because.', anchor: 'Need' }],
	'explanation-block': [{ body: 'Explain.', emphasis: [] }],
	'prerequisite-strip': [{ items: [{ concept: 'Prior idea' }] }],
	'what-next-bridge': [{ body: 'Next unit builds on this.', next: 'Quadratics', preview: 'Preview.' }],
	'interview-anchor': [{ prompt: 'Explain to a peer.', audience: 'Friend' }],
	'callout-block': [{ variant: 'tip', body: 'Notice this.' }],
	'summary-block': [{ items: [{ text: 'Idea one' }, { text: 'Idea two' }] }],
	'section-divider': [{ label: 'Part B' }],
	'definition-card': [{ term: 'Term', formal: 'Formal def.', plain: 'Plain def.' }],
	'definition-family': [
		{
			family_title: 'Related',
			definitions: [{ term: 'A', formal: 'FA', plain: 'PA' }]
		}
	],
	'glossary-rail': [
		{
			terms: [{ term: 'Omega', definition: 'A Greek letter commonly used as a variable.' }]
		}
	],
	'glossary-inline': [{ term: 'Term', definition: 'Short gloss.' }],
	'insight-strip': [
		{
			cells: [
				{ label: 'A', value: '1' },
				{ label: 'B', value: '2' }
			]
		}
	],
	'key-fact': [{ fact: 'E = mc²' }],
	'comparison-grid': [
		{
			title: 'Compare',
			columns: [{ id: 'c1', title: 'A', summary: 'SA' }],
			rows: [{ criterion: 'Speed', values: ['Fast'], takeaway: '' }]
		}
	],
	'worked-example-card': [
		{
			title: 'Demo',
			setup: 'Problem setup.',
			steps: [{ label: 'Step 1', content: 'Do this.' }],
			conclusion: 'Done.'
		}
	],
	'process-steps': [{ title: 'Method', steps: [{ number: 1, action: 'Start', detail: 'Details.' }] }],
	'practice-stack': [
		{
			problems: [
				{
					difficulty: 'warm',
					question: 'Try this.',
					hints: [{ level: 1, text: 'Hint one' }]
				},
				{
					difficulty: 'medium',
					question: 'Try that.',
					hints: [{ level: 1, text: 'Hint one' }]
				}
			]
		}
	],
	'quiz-check': [
		{
			question: 'Pick one.',
			options: [
				{ text: 'A', correct: false, explanation: 'No.' },
				{ text: 'B', correct: true, explanation: 'Yes.' },
				{ text: 'C', correct: false, explanation: 'No.' }
			],
			feedback_correct: 'Nice.',
			feedback_incorrect: 'Review.'
		}
	],
	'reflection-prompt': [{ prompt: 'Think briefly.', type: 'open' }],
	'student-textbox': [{ prompt: 'Write notes.' }],
	'short-answer': [{ question: 'Explain inertia in one paragraph.' }],
	'fill-in-blank': [
		{
			segments: [
				{ text: 'The answer is ', is_blank: false },
				{ text: '', is_blank: true, answer: 'x' }
			]
		}
	],
	'pitfall-alert': [{ misconception: 'Wrong idea', correction: 'Right idea.' }],
	'diagram-block': [
		{
			caption: 'A labelled diagram for the lesson.',
			alt_text: 'Diagram showing key parts referenced in the prose.'
		}
	],
	'diagram-compare': [
		{
			before_label: 'Before',
			after_label: 'After',
			caption: 'Compare both states.',
			alt_text: 'Side-by-side diagram comparison.'
		}
	],
	'diagram-series': [
		{
			title: 'Steps',
			diagrams: [
				{
					step_label: '1',
					caption: 'First frame.',
					svg_content: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
				}
			]
		}
	],
	'video-embed': [{ media_id: 'demo-media', print_fallback: 'thumbnail' }],
	'image-block': [
		{
			media_id: 'img-1',
			alt_text: 'Alt text describing the instructional image.',
			caption: 'Figure 1.'
		}
	],
	'timeline-block': [
		{
			title: 'Timeline',
			events: [
				{
					id: 'e1',
					year: '1066',
					title: 'Event',
					summary: 'What happened.'
				}
			]
		}
	],
	'simulation-block': [
		{
			spec: {
				type: 'sandbox',
				goal: 'Explore the slider effect on the graph.',
				anchor_content: {},
				context: {
					learner_level: 'secondary',
					template_id: 'sandbox',
					color_mode: 'light',
					accent_color: '#0f172a',
					surface_color: '#ffffff',
					font_mono: 'ui-monospace'
				},
				dimensions: { width: '100%', height: 420, resizable: true },
				print_translation: 'static_diagram'
			}
		}
	]
};

function schemaTs(sectionField: string | null, componentId: string): string {
	if (componentId === 'glossary-inline') {
		return `import { GlossaryInlineSchema as componentSchema } from '$lib/lectio/schemas/content-zod';

export { componentSchema };
`;
	}

	if (sectionField === null) throw new Error(`Missing schema mapping for "${componentId}"`);

	return `import { SCHEMA_BY_SECTION_FIELD } from '$lib/lectio/schemas/content-zod';

export const componentSchema = SCHEMA_BY_SECTION_FIELD['${sectionField}'];
`;
}

function escSingleQuotes(value: string): string {
	return value.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

mkdirSync(COMPONENTS, { recursive: true });

const imports: Array<{ slug: string; varName: string }> = [];
let ordinal = 0;

for (const [registryKey, legacy] of Object.entries(legacyRegistry)) {
	const slug = legacy.id;
	const varName = `cm${ordinal++}`;
	imports.push({ slug, varName });

	const dir = resolve(COMPONENTS, slug);
	mkdirSync(dir, { recursive: true });
	try {
		unlinkSync(resolve(dir, 'index.ts'));
	} catch {
		// ignore missing legacy index.ts
	}

	const caps = capsFor(slug);
	const print = printFor(slug, legacy.printFallback);

	const behaviourModesLiteral = `[${legacy.behaviourModes.map((b) => `'${b}'`).join(', ')}] as const`;

	const metadataTs =
		`import type { LectioComponentPublicMetadata } from '$lib/lectio/core/types';\n` +
		`import type { BehaviourMode } from '$lib/schema/types';\n\n` +
		`export const metadata = {\n` +
		`\tregistryKey: '${escSingleQuotes(registryKey)}',\n` +
		`\tid: '${legacy.id}',\n` +
		`\tname: '${escSingleQuotes(legacy.name)}',\n` +
		`\tphase: ${legacy.group},\n\n` +
		`\trole: ${JSON.stringify(legacy.purpose)},\n\n` +
		`\tcognitiveJob: ${JSON.stringify(legacy.cognitiveJob)},\n` +
		`\tsubjects: ${JSON.stringify(legacy.subjects)},\n` +
		`\tbehaviourModes: ${behaviourModesLiteral} satisfies readonly BehaviourMode[],\n\n` +
		`\tcapabilities: ${JSON.stringify(caps)},\n` +
		`\tcapacity: ${JSON.stringify(legacy.capacity)},\n\n` +
		`\tstatus: '${legacy.status}',\n` +
		`\tsectionField: ${legacy.sectionField === null ? 'null' : `'${legacy.sectionField}'`},\n` +
		`\tshadcnPrimitive: ${JSON.stringify(legacy.shadcnPrimitive)}` +
		(legacy.generationHint ? `,\n\tgenerationHint: ${JSON.stringify(legacy.generationHint)}` : '') +
		`\n} satisfies LectioComponentPublicMetadata;\n`;

	const examples = EXAMPLES[slug];
	if (!examples) throw new Error(`Missing EXAMPLES entry for "${slug}"`);

	const printTs =
		`import type { LectioPrintSpec } from '$lib/lectio/core/types';\n\n` +
		`export const print = ${JSON.stringify(print, null, '\t')} satisfies LectioPrintSpec;\n`;

	const examplesTs =
		`import type { z } from 'zod';\n` +
		`import { componentSchema } from './schema';\n\n` +
		`type ExampleDatum = z.infer<typeof componentSchema>;\n\n` +
		`export const examples: ExampleDatum[] = ${JSON.stringify(examples, null, '\t')};\n`;

	const componentSvelte =
		`<script lang="ts">\n` +
		`\timport Inner from '$lib/components/lectio/${registryKey}.svelte';\n` +
		`\tlet props = $props();\n` +
		`</script>\n\n` +
		`<Inner {...props} />\n`;

	const moduleTs =
		`import { componentSchema } from './schema';\n` +
		`import { metadata } from './metadata';\n` +
		`import { print } from './print';\n` +
		`import { examples } from './examples';\n` +
		`import type { LectioContentModule } from '$lib/lectio/core/types';\n\n` +
		`export const lectioModule = {\n` +
		`\tschema: componentSchema,\n` +
		`\tmetadata,\n` +
		`\tprint,\n` +
		`\texamples\n` +
		`} satisfies LectioContentModule;\n`;

	writeFileSync(resolve(dir, 'metadata.ts'), metadataTs, 'utf8');
	writeFileSync(resolve(dir, 'print.ts'), printTs, 'utf8');
	writeFileSync(resolve(dir, 'examples.ts'), examplesTs, 'utf8');
	writeFileSync(resolve(dir, 'schema.ts'), schemaTs(legacy.sectionField, slug), 'utf8');
	writeFileSync(resolve(dir, 'Component.svelte'), componentSvelte, 'utf8');
	writeFileSync(resolve(dir, 'module.ts'), moduleTs, 'utf8');
}

const componentsTsLines: string[] = [];
componentsTsLines.push(`import type { LectioContentModule } from '$lib/lectio/core/types';`);
componentsTsLines.push(`import { buildLegacyComponentRegistryFromModules } from './build-legacy-registry';`);
componentsTsLines.push(``);

for (const row of imports) {
	const folderImport = `../components/${row.slug}`;
	componentsTsLines.push(`import { lectioModule as ${row.varName} } from '${folderImport}/module';`);
}

componentsTsLines.push(``);

componentsTsLines.push(
	`/** Ordered list mirrors legacy \`registry.ts\` insertion order for stable manifests/exports */\nexport const lectioContentModules = [`
);
componentsTsLines.push(imports.map((r) => `\t${r.varName}`).join(',\n'));
componentsTsLines.push(`] as const satisfies readonly LectioContentModule[];`);
componentsTsLines.push(``);
componentsTsLines.push(
	`/** Alias kept for the v3 proposal wording — these modules exclude Svelte */\nexport const lectioComponentModules = lectioContentModules;`
);
componentsTsLines.push(`export const lectioComponents = lectioContentModules;`);
componentsTsLines.push(`export type LectioContentModuleList = typeof lectioContentModules;`);
componentsTsLines.push(`export type LectioComponentModuleList = LectioContentModuleList;`);
componentsTsLines.push(``);

componentsTsLines.push(
	`/**\n * Legacy registry map keyed by PascalCase importer token (historical \`src/lib/components/lectio/*.svelte\` naming).\n * Built from Lectio modules; includes normalized generation hints.\n */`
);
componentsTsLines.push(`export const componentRegistry = buildLegacyComponentRegistryFromModules([...lectioContentModules]);`);

writeFileSync(resolve(REGISTRY_DIR, 'components.ts'), componentsTsLines.join('\n') + `\n`, 'utf8');

// eslint-disable-next-line no-console
console.log(`Bootstrapped ${imports.length} component modules under ${COMPONENTS}`);
// eslint-disable-next-line no-console
console.log(`Wrote ${resolve(REGISTRY_DIR, 'components.ts')}`);
