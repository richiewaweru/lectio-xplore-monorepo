<script lang="ts">
	import type { Snippet } from 'svelte';

	type Tone = 'neutral' | 'ready' | 'attention' | 'danger' | 'info';

	interface Props {
		tone?: Tone;
		children?: Snippet;
	}

	let { tone = 'neutral', children }: Props = $props();
</script>

<span class="badge badge-{tone}">
	{#if children}{@render children()}{/if}
</span>

<style>
	.badge {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.2rem 0.55rem;
		border-radius: 999px;
		font-size: 0.75rem;
		font-weight: 550;
		letter-spacing: 0.01em;
		line-height: 1.3;
	}
	.badge-neutral {
		background: var(--surface-2);
		color: var(--ink-2);
	}
	.badge-ready {
		background: var(--success-soft);
		color: var(--success);
	}
	.badge-attention {
		background: var(--amber-soft);
		color: var(--amber);
	}
	.badge-danger {
		background: var(--danger-soft);
		color: var(--danger);
	}
	.badge-info {
		background: var(--accent-soft);
		color: var(--accent);
	}
</style>
