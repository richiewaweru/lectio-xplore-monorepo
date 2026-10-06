<script lang="ts">
	import type { HeadingContent } from '$lib/contract/document';
	import { asRichText } from '$lib/normalize/inline';
	import InlineView from '../InlineView.svelte';

	let { content }: { content: HeadingContent } = $props();

	const level = $derived(Number(content.level));
	const text = $derived(asRichText(content.text));
</script>

{#if level === 1}
	<!-- Document title owns h1; clamp stray level-1 nested headings to h3. -->
	<h3>{#if content.number}{content.number} {/if}<InlineView nodes={text} /></h3>
{:else if level === 2}
	<!-- Section title owns h2; nested heading blocks render as h3. -->
	<h3>{#if content.number}{content.number} {/if}<InlineView nodes={text} /></h3>
{:else}
	<h3>{#if content.number}{content.number} {/if}<InlineView nodes={text} /></h3>
{/if}
