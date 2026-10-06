<script lang="ts">
	import InlineMarkup from './InlineMarkup.svelte';

	interface Props { node: Record<string, unknown>; }
	let { node }: Props = $props();
	const learnerFields = [
		'text', 'body', 'title', 'content', 'label', 'belief', 'evidence',
		'conclusion', 'aside', 'caption', 'attribution'
	] as const;
	const paragraphs = $derived(
		learnerFields
			.flatMap((field) => {
				const value = node[field];
				return typeof value === 'string' && value.trim().length > 0 ? [value] : [];
			})
			.flatMap((value) => value.split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean))
	);
</script>

{#each paragraphs as paragraph (paragraph)}
	<p class="unknown-fallback"><InlineMarkup value={paragraph} /></p>
{/each}

<style>
	.unknown-fallback { margin: 0; font-size: 18px; line-height: 1.6; }
	.unknown-fallback + .unknown-fallback { margin-top: 18px; }
</style>
