<script lang="ts">
	import type { DocumentBlock } from '$lib/contract/document';
	import HeadingView from './objects/HeadingView.svelte';
	import ProseView from './objects/ProseView.svelte';
	import ListView from './objects/ListView.svelte';
	import TableView from './objects/TableView.svelte';
	import FigureView from './objects/FigureView.svelte';
	import AsideView from './objects/AsideView.svelte';
	import EquationView from './objects/EquationView.svelte';
	import QuoteView from './objects/QuoteView.svelte';
	import CompareView from './objects/CompareView.svelte';
	import WorkedExampleView from './objects/WorkedExampleView.svelte';
	import QuestionsView from './objects/QuestionsView.svelte';
	import ChoicesView from './objects/ChoicesView.svelte';
	import AnswerKeyView from './objects/AnswerKeyView.svelte';

	let { block, figureNumber }: { block: DocumentBlock; figureNumber?: number } = $props();
	const warnedUnknownKinds = new Set<string>();

	function fallbackText(value: unknown): string {
		if (typeof value === 'string') return value;
		if (Array.isArray(value)) return value.map(fallbackText).filter(Boolean).join(' ');
		if (!value || typeof value !== 'object') return '';
		const record = value as Record<string, unknown>;
		const preferred = ['text', 'body', 'title', 'label', 'caption', 'prompt', 'description'];
		const selected = preferred.map((key) => record[key]).filter((entry) => entry != null);
		if (selected.length) return selected.map(fallbackText).filter(Boolean).join(' ');
		return Object.values(record).map(fallbackText).filter(Boolean).join(' ');
	}

	function renderUnknownBlock(): string {
		const raw = block as unknown as { object?: unknown; content?: unknown };
		const kind = String(raw.object ?? 'unknown');
		if (!warnedUnknownKinds.has(kind)) {
			warnedUnknownKinds.add(kind);
			console.warn(`[Lectio Page] unknown block kind "${kind}" rendered as text`);
		}
		return fallbackText(raw.content);
	}

	/**
	 * `aside` defaults to margin when placement is absent, preserving the
	 * pre-change rendering of every existing persisted document. Every other
	 * object defaults to main. object-catalogue.v1.json is the authority on
	 * which objects may take 'margin' — validation already enforces it.
	 */
	const placement = $derived(
		block.layout?.placement ?? (block.object === 'aside' ? 'margin' : 'main')
	);
	const spanning = $derived(placement === 'spanning');
	const inMargin = $derived(placement === 'margin');
</script>

{#if block.object === 'heading'}
	<HeadingView content={block.content} />
{:else if block.object === 'prose'}
	<ProseView content={block.content} />
{:else if block.object === 'list'}
	<ListView content={block.content} {inMargin} />
{:else if block.object === 'table'}
	<TableView content={block.content} {spanning} />
{:else if block.object === 'figure'}
	<FigureView content={block.content} {spanning} {figureNumber} />
{:else if block.object === 'aside'}
	<AsideView content={block.content} inMargin={inMargin && !spanning} spanning={spanning} />
{:else if block.object === 'equation'}
	<EquationView content={block.content} />
{:else if block.object === 'quote'}
	<QuoteView content={block.content} />
{:else if block.object === 'compare'}
	<CompareView content={block.content} />
{:else if block.object === 'worked-example'}
	<WorkedExampleView content={block.content} />
{:else if block.object === 'questions'}
	<QuestionsView content={block.content} role={block.role ?? ''} />
{:else if block.object === 'choices'}
	<ChoicesView content={block.content} questionId={block.id} role={block.role ?? ''} />
{:else if block.object === 'answer-key'}
	<AnswerKeyView content={block.content} />
{:else}
	<p class="lectio-unknown-block">{renderUnknownBlock()}</p>
{/if}
