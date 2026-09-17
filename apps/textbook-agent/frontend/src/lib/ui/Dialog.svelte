<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		open: boolean;
		title: string;
		description?: string;
		onClose?: () => void;
		children?: Snippet;
		footer?: Snippet;
	}

	let { open = $bindable(false), title, description, onClose, children, footer }: Props = $props();

	function close() {
		open = false;
		onClose?.();
	}

	function onKey(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) close();
	}
</script>

<svelte:window onkeydown={onKey} />

{#if open}
	<div class="backdrop" role="presentation" onclick={close}>
		<div
			class="panel"
			role="dialog"
			tabindex="-1"
			aria-modal="true"
			aria-labelledby="dialog-title"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
		>
			<header>
				<h2 id="dialog-title">{title}</h2>
				{#if description}
					<p class="desc">{description}</p>
				{/if}
				<button type="button" class="close" aria-label="Close" onclick={close}>×</button>
			</header>
			<div class="body">
				{#if children}{@render children()}{/if}
			</div>
			{#if footer}
				<footer>{@render footer()}</footer>
			{/if}
		</div>
	</div>
{/if}

<style>
	.backdrop {
		position: fixed;
		inset: 0;
		z-index: 80;
		display: grid;
		place-items: center;
		padding: var(--space-4);
		background: rgba(22, 33, 28, 0.35);
		backdrop-filter: blur(4px);
	}
	.panel {
		width: min(480px, 100%);
		max-height: min(90vh, 720px);
		overflow: auto;
		background: var(--surface);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-md);
		border: 1px solid var(--rule);
	}
	header {
		position: relative;
		padding: var(--space-5) var(--space-6) var(--space-3);
	}
	h2 {
		margin: 0;
		font-size: 1.15rem;
		font-weight: 600;
		padding-right: 2rem;
	}
	.desc {
		margin: 0.35rem 0 0;
		color: var(--ink-2);
		font-size: 0.875rem;
	}
	.close {
		position: absolute;
		top: 0.85rem;
		right: 0.85rem;
		border: none;
		background: transparent;
		font-size: 1.4rem;
		line-height: 1;
		color: var(--ink-3);
		cursor: pointer;
		padding: 0.25rem 0.4rem;
		border-radius: var(--radius-sm);
	}
	.close:hover {
		background: var(--surface-2);
		color: var(--ink);
	}
	.body {
		padding: 0 var(--space-6) var(--space-5);
	}
	footer {
		display: flex;
		justify-content: flex-end;
		gap: var(--space-2);
		padding: var(--space-3) var(--space-6) var(--space-5);
		border-top: 1px solid var(--rule);
	}
</style>
