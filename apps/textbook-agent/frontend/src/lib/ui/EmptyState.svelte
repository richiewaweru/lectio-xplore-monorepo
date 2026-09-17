<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		description?: string;
		actions?: Snippet;
	}

	let { title, description, actions }: Props = $props();
</script>

<div class="empty">
	<h2>{title}</h2>
	{#if description}
		<p>{description}</p>
	{/if}
	{#if actions}
		<div class="actions">{@render actions()}</div>
	{/if}
</div>

<style>
	.empty {
		padding: var(--space-10) var(--space-6);
		text-align: center;
		border: 1px dashed var(--rule);
		border-radius: var(--radius-lg);
		background: color-mix(in srgb, var(--surface) 70%, var(--paper));
	}
	h2 {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 600;
		color: var(--ink);
	}
	p {
		margin: var(--space-2) auto 0;
		max-width: 28rem;
		color: var(--ink-2);
		font-size: 0.9rem;
		line-height: 1.5;
	}
	.actions {
		margin-top: var(--space-4);
		display: flex;
		justify-content: center;
		gap: var(--space-2);
	}
</style>
