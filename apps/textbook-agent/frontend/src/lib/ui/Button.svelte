<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';

	type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
	type Size = 'sm' | 'md' | 'lg';

	interface Props extends HTMLButtonAttributes {
		variant?: Variant;
		size?: Size;
		busy?: boolean;
		children?: Snippet;
	}

	let {
		variant = 'primary',
		size = 'md',
		busy = false,
		disabled,
		class: className = '',
		children,
		type = 'button',
		...rest
	}: Props = $props();
</script>

<button
	{type}
	class="btn btn-{variant} btn-{size} {className}"
	disabled={disabled || busy}
	aria-busy={busy || undefined}
	{...rest}
>
	{#if children}{@render children()}{/if}
</button>

<style>
	.btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		border-radius: var(--radius-md);
		border: 1px solid transparent;
		font-family: var(--font-sans);
		font-weight: 550;
		cursor: pointer;
		text-decoration: none;
		white-space: nowrap;
		transition:
			background 0.12s ease,
			border-color 0.12s ease,
			color 0.12s ease,
			opacity 0.12s ease;
	}
	.btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}
	.btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.btn-sm {
		padding: 0.35rem 0.7rem;
		font-size: 0.8125rem;
	}
	.btn-md {
		padding: 0.55rem 1rem;
		font-size: 0.875rem;
	}
	.btn-lg {
		padding: 0.7rem 1.25rem;
		font-size: 0.9375rem;
	}
	.btn-primary {
		background: var(--accent);
		color: #fff;
	}
	.btn-primary:hover:not(:disabled) {
		background: var(--accent-hover);
	}
	.btn-secondary {
		background: var(--surface);
		border-color: var(--rule);
		color: var(--ink);
	}
	.btn-secondary:hover:not(:disabled) {
		background: var(--surface-2);
	}
	.btn-ghost {
		background: transparent;
		color: var(--ink-2);
	}
	.btn-ghost:hover:not(:disabled) {
		background: var(--accent-soft);
		color: var(--accent);
	}
	.btn-danger {
		background: var(--danger-soft);
		color: var(--danger);
		border-color: color-mix(in srgb, var(--danger) 20%, transparent);
	}
</style>
