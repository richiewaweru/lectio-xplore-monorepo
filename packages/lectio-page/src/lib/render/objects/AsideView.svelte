<script lang="ts">
	import type { AsideContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content, inMargin = false, spanning = false }: { content: AsideContent; inMargin?: boolean; spanning?: boolean } = $props();
	const variantClass = $derived(content.variant ? `lectio-aside--${content.variant}` : '');
</script>

<aside class={['lectio-aside', inMargin && 'lectio-block--margin', spanning && 'lectio-aside--spanning', variantClass]}>
	{#if content.label && content.variant !== 'misconception'}
		<strong class="lectio-aside-label"><InlineView nodes={asRichText(content.label)} /></strong><br />
	{/if}
	{#if content.variant === 'misconception' && content.belief && content.evidence && content.conclusion}
		<div class="lectio-misconception-grid">
			{#if content.label}<div class="lectio-misconception-label"><strong><InlineView nodes={asRichText(content.label)} /></strong></div>{/if}
			<div class="lectio-misconception-row"><strong>The belief</strong><q><InlineView nodes={asRichText(content.belief)} /></q></div>
			<div class="lectio-misconception-row"><strong>The evidence</strong><InlineView nodes={asRichText(content.evidence)} /></div>
			<div class="lectio-misconception-row"><strong>So</strong><InlineView nodes={asRichText(content.conclusion)} /></div>
		</div>
		{#if content.aside}<p class="lectio-aside-followup"><InlineView nodes={asRichText(content.aside)} /></p>{/if}
	{:else}
		{#if content.variant === 'key_idea'}
			<span class="lectio-aside-body"><InlineView nodes={asRichText(content.body)} /></span>
		{:else}
			<InlineView nodes={asRichText(content.body)} />
		{/if}
		{#if content.aside}
			<p class="lectio-aside-followup"><InlineView nodes={asRichText(content.aside)} /></p>
		{/if}
	{/if}
</aside>
