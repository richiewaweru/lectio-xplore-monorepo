<script lang="ts">
	import type { DocumentBlock } from '$lib/contract/document';
	import HeadingView from './objects/HeadingView.svelte';
	import ProseView from './objects/ProseView.svelte';
	import ListView from './objects/ListView.svelte';
	import TableView from './objects/TableView.svelte';
	import FigureView from './objects/FigureView.svelte';
	import AsideView from './objects/AsideView.svelte';
	import WorkedExampleView from './objects/WorkedExampleView.svelte';
	import QuestionsView from './objects/QuestionsView.svelte';
	import ChoicesView from './objects/ChoicesView.svelte';
	import AnswerKeyView from './objects/AnswerKeyView.svelte';

	let { block }: { block: DocumentBlock } = $props();

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
	<FigureView content={block.content} {spanning} />
{:else if block.object === 'aside'}
	<AsideView content={block.content} {inMargin} />
{:else if block.object === 'worked-example'}
	<WorkedExampleView content={block.content} />
{:else if block.object === 'questions'}
	<QuestionsView content={block.content} />
{:else if block.object === 'choices'}
	<ChoicesView content={block.content} />
{:else if block.object === 'answer-key'}
	<AnswerKeyView content={block.content} />
{/if}
