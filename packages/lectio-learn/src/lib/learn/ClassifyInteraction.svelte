<script lang="ts">
	import { evaluateMatchPairs, type FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Item {
		id: string;
		label: string;
	}
	interface Category {
		id: string;
		label: string;
	}

	interface Props {
		prompt: string;
		items: Item[];
		categories: Category[];
		correctPairs: Array<{ left: string; right: string }>;
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let { prompt, items, categories, correctPairs, feedback, ariaLabel = prompt }: Props = $props();

	let selectedItem = $state<string | null>(null);
	let matches = $state<Array<{ left: string; right: string }>>([]);
	let submitted = $state(false);

	const result = $derived(
		submitted ? evaluateMatchPairs({ pairs: correctPairs }, { matches }, feedback) : null
	);

	function pickItem(id: string) {
		if (submitted) return;
		selectedItem = id;
	}
	function pickCategory(id: string) {
		if (submitted || !selectedItem) return;
		matches = [
			...matches.filter((m) => m.left !== selectedItem),
			{ left: selectedItem, right: id }
		];
		selectedItem = null;
	}
</script>

<div class="classify-root" aria-label={ariaLabel} data-testid="classify-interaction">
	<p class="prompt">{prompt}</p>
	<ul class="items">
		{#each items as item (item.id)}
			<li>
				<button
					type="button"
					class="chip"
					class:selected={selectedItem === item.id}
					class:matched={matches.some((m) => m.left === item.id)}
					disabled={submitted}
					onclick={() => pickItem(item.id)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							pickItem(item.id);
						}
					}}
				>
					{item.label}
				</button>
			</li>
		{/each}
	</ul>
	<ul class="cats">
		{#each categories as cat (cat.id)}
			<li>
				<button
					type="button"
					class="chip cat"
					disabled={submitted || !selectedItem}
					onclick={() => pickCategory(cat.id)}
					onkeydown={(e) => {
						if (e.key === 'Enter' || e.key === ' ') {
							e.preventDefault();
							pickCategory(cat.id);
						}
					}}
				>
					{cat.label}
					{#if matches.some((m) => m.right === cat.id)}
						<span class="count">{matches.filter((m) => m.right === cat.id).length}</span>
					{/if}
				</button>
			</li>
		{/each}
	</ul>
	<button type="button" class="submit" disabled={submitted || matches.length === 0} onclick={() => (submitted = true)}>
		Check
	</button>
	{#if result}
		<p class="feedback" data-outcome={result.outcome} role="status">{result.feedback}</p>
	{/if}
</div>

<style>
	.classify-root {
		display: grid;
		gap: 12px;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 12px;
		background: var(--surface, #fff);
		padding: 14px;
		color: var(--ink, #1c1917);
	}
	.prompt {
		margin: 0;
		font-weight: 600;
	}
	.items,
	.cats {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.chip {
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 999px;
		background: var(--paper, #fafaf9);
		padding: 8px 12px;
		cursor: pointer;
	}
	.chip.selected,
	.chip.matched {
		border-color: var(--accent, #0f766e);
		background: color-mix(in srgb, var(--accent, #0f766e) 12%, white);
	}
	.cat .count {
		margin-left: 6px;
		font: 500 11px 'IBM Plex Mono', monospace;
	}
	.submit {
		justify-self: start;
		border: 1px solid var(--accent, #0f766e);
		border-radius: 8px;
		background: var(--accent, #0f766e);
		color: white;
		padding: 8px 12px;
		font-weight: 600;
		cursor: pointer;
	}
	.feedback {
		margin: 0;
		font-size: 14px;
	}
</style>
