<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		eyebrow?: string;
		description?: string;
		actions?: Snippet;
		breadcrumb?: Snippet;
	}

	let { title, eyebrow, description, actions, breadcrumb }: Props = $props();
</script>

<header class="page-header">
	<div class="copy">
		{#if breadcrumb}
			<nav class="crumb" aria-label="Breadcrumb">{@render breadcrumb()}</nav>
		{/if}
		{#if eyebrow}
			<p class="eyebrow">{eyebrow}</p>
		{/if}
		<h1>{title}</h1>
		{#if description}
			<p class="desc">{description}</p>
		{/if}
	</div>
	{#if actions}
		<div class="actions">{@render actions()}</div>
	{/if}
</header>

<style>
	.page-header {
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--space-4);
		margin-bottom: var(--space-6);
	}
	.eyebrow {
		margin: 0 0 var(--space-1);
		color: var(--ink-3);
		font-size: 0.75rem;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0;
		font-family: var(--font-serif);
		font-size: 1.75rem;
		font-weight: 600;
		letter-spacing: -0.02em;
		line-height: 1.2;
		color: var(--ink);
	}
	.desc {
		margin: var(--space-2) 0 0;
		color: var(--ink-2);
		font-size: 0.9375rem;
		max-width: 42rem;
		line-height: 1.5;
	}
	.crumb {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		align-items: center;
		margin-bottom: var(--space-2);
		color: var(--ink-3);
		font-size: 0.8125rem;
	}
	.crumb :global(a) {
		color: var(--ink-2);
		text-decoration: none;
	}
	.crumb :global(a:hover) {
		color: var(--accent);
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		align-items: center;
	}
</style>
