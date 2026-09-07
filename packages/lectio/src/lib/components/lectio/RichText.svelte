<script lang="ts">
	import { renderInlineMarkdown } from '$lib/utils/markdown';

	let {
		text,
		class: className = '',
		tag = 'span'
	}: {
		text: string;
		class?: string;
		tag?: 'span' | 'p' | 'div';
	} = $props();
</script>

{#if tag === 'p'}
	<p class={className}>{@html renderInlineMarkdown(text)}</p>
{:else if tag === 'div'}
	<div class={className}>{@html renderInlineMarkdown(text)}</div>
{:else}
	<span class={className}>{@html renderInlineMarkdown(text)}</span>
{/if}
