<script lang="ts">
	import { parseInlineMarkup, type InlineNode } from '../inline';
	import InlineMarkup from './InlineMarkup.svelte';

	interface Props {
		value?: string | null;
		nodes?: InlineNode[];
	}

	let { value = '', nodes = undefined }: Props = $props();
	const parsed = $derived(nodes ?? parseInlineMarkup(value ?? ''));
</script>

{#each parsed as node}
	{#if node.type === 'text'}
		{node.value}
	{:else if node.type === 'strong'}
		<strong><InlineMarkup nodes={node.children} /></strong>
	{:else if node.type === 'emphasis'}
		<em><InlineMarkup nodes={node.children} /></em>
	{:else if node.type === 'subscript'}
		<sub><InlineMarkup nodes={node.children} /></sub>
	{:else if node.type === 'superscript'}
		<sup><InlineMarkup nodes={node.children} /></sup>
	{/if}
{/each}
