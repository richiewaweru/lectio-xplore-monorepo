<script lang="ts">
	interface Tab {
		id: string;
		label: string;
		href?: string;
	}

	interface Props {
		tabs: Tab[];
		active: string;
		onSelect?: (id: string) => void;
	}

	let { tabs, active, onSelect }: Props = $props();
</script>

<div class="tabs" role="tablist">
	{#each tabs as tab}
		{#if tab.href}
			<a
				href={tab.href}
				class="tab"
				class:active={tab.id === active}
				aria-current={tab.id === active ? 'page' : undefined}
			>
				{tab.label}
			</a>
		{:else}
			<button
				type="button"
				class="tab"
				class:active={tab.id === active}
				role="tab"
				aria-selected={tab.id === active}
				onclick={() => onSelect?.(tab.id)}
			>
				{tab.label}
			</button>
		{/if}
	{/each}
</div>

<style>
	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.15rem;
		border-bottom: 1px solid var(--rule);
		margin-bottom: var(--space-5);
	}
	.tab {
		appearance: none;
		border: none;
		background: transparent;
		padding: 0.7rem 0.95rem;
		font: inherit;
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--ink-2);
		cursor: pointer;
		text-decoration: none;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		border-radius: var(--radius-sm) var(--radius-sm) 0 0;
	}
	.tab:hover {
		color: var(--ink);
	}
	.tab.active {
		color: var(--accent);
		border-bottom-color: var(--accent);
	}
	.tab:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
