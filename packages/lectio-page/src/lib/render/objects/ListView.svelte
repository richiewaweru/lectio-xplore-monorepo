<script lang="ts">
	import type { ListContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content, inMargin = false }: { content: ListContent; inMargin?: boolean } = $props();

	const ordered = $derived(content.style === 'ordered' || content.style === 'steps');
	const lead = $derived(asRichText(content.lead_in ?? null));
</script>

{#if lead.length}
	<p><InlineView nodes={lead} /></p>
{/if}

{#if ordered}
	<ol class={['lectio-list', inMargin && 'lectio-block--margin']}>
		{#each content.items as item}
			<li><InlineView nodes={asRichText(item.text)} /></li>
		{/each}
	</ol>
{:else}
	<ul class={['lectio-list', inMargin && 'lectio-block--margin']}>
		{#each content.items as item}
			<li><InlineView nodes={asRichText(item.text)} /></li>
		{/each}
	</ul>
{/if}
