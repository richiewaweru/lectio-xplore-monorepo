<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		padding?: 'sm' | 'md' | 'lg';
		children?: Snippet;
		href?: string;
	}

	let { padding = 'md', class: className = '', children, href, ...rest }: Props = $props();
</script>

{#if href}
	<a {href} class="card card-{padding} {className}" {...rest as any}>
		{#if children}{@render children()}{/if}
	</a>
{:else}
	<div class="card card-{padding} {className}" {...rest}>
		{#if children}{@render children()}{/if}
	</div>
{/if}

<style>
	.card {
		display: block;
		background: var(--surface);
		border: 1px solid var(--rule);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-sm);
		color: inherit;
		text-decoration: none;
	}
	a.card:hover {
		border-color: color-mix(in srgb, var(--accent) 35%, var(--rule));
		box-shadow: var(--shadow-md);
	}
	.card-sm {
		padding: var(--space-4);
	}
	.card-md {
		padding: var(--space-6);
	}
	.card-lg {
		padding: var(--space-8);
	}
</style>
