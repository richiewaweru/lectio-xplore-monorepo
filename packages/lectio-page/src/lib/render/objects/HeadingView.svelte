<script lang="ts">
	import type { HeadingContent } from '$lib/contract/document';

	let { content }: { content: HeadingContent } = $props();

	const level = $derived(Number(content.level));
	const text = $derived(content.number ? `${content.number} ${content.text}` : content.text);
</script>

{#if level === 1}
	<!-- Document title owns h1; clamp stray level-1 nested headings to h3. -->
	<h3>{text}</h3>
{:else if level === 2}
	<!-- Section title owns h2; nested heading blocks render as h3. -->
	<h3>{text}</h3>
{:else}
	<h3>{text}</h3>
{/if}
