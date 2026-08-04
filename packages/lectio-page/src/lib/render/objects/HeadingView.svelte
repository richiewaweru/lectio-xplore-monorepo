<script lang="ts">
	import type { HeadingContent } from '$lib/contract/document';

	let { content }: { content: HeadingContent } = $props();

	const level = $derived(Number(content.level));
	const text = $derived(content.number ? `${content.number} ${content.text}` : content.text);
</script>

{#if level === 1}
	<h1>{text}</h1>
{:else if level === 3}
	<h3>{text}</h3>
{:else}
	<h2>{text}</h2>
{/if}
