<script lang="ts">
	import { evaluateMatchPairs, type FeedbackSpec } from '$lib/learn/interaction-contract';

	interface PairSide {
		id: string;
		label: string;
	}

	interface Props {
		prompt: string;
		left: PairSide[];
		right: PairSide[];
		correctPairs: Array<{ left: string; right: string }>;
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let { prompt, left, right, correctPairs, feedback, ariaLabel = prompt }: Props = $props();

	let selectedLeft = $state<string | null>(null);
	let matches = $state<Array<{ left: string; right: string }>>([]);
	let submitted = $state(false);

	const result = $derived(
		submitted
			? evaluateMatchPairs({ pairs: correctPairs }, { matches }, feedback)
			: null
	);

	function pickLeft(id: string) {
		if (submitted) return;
		selectedLeft = id;
	}

	function pickRight(id: string) {
		if (submitted || !selectedLeft) return;
		matches = [...matches.filter((m) => m.left !== selectedLeft && m.right !== id), { left: selectedLeft, right: id }];
		selectedLeft = null;
	}

	function onKeyLeft(e: KeyboardEvent, id: string) {
		if (e.key === ' ' || e.key === 'Enter') {
			e.preventDefault();
			pickLeft(id);
		}
	}
	function onKeyRight(e: KeyboardEvent, id: string) {
		if (e.key === ' ' || e.key === 'Enter') {
			e.preventDefault();
			pickRight(id);
		}
	}
</script>

<div class="match-root" aria-label={ariaLabel} data-testid="match-interaction">
	<p class="prompt">{prompt}</p>
	<div class="columns">
		<ul class="col">
			{#each left as item (item.id)}
				<li>
					<button
						type="button"
						class="chip"
						class:selected={selectedLeft === item.id}
						class:matched={matches.some((m) => m.left === item.id)}
						disabled={submitted}
						onclick={() => pickLeft(item.id)}
						onkeydown={(e) => onKeyLeft(e, item.id)}
					>
						{item.label}
					</button>
				</li>
			{/each}
		</ul>
		<ul class="col">
			{#each right as item (item.id)}
				<li>
					<button
						type="button"
						class="chip"
						class:matched={matches.some((m) => m.right === item.id)}
						disabled={submitted || !selectedLeft}
						onclick={() => pickRight(item.id)}
						onkeydown={(e) => onKeyRight(e, item.id)}
					>
						{item.label}
					</button>
				</li>
			{/each}
		</ul>
	</div>
	<p class="hint">Select a left item, then a right item to pair them.</p>
	<button type="button" class="submit" disabled={submitted || matches.length === 0} onclick={() => (submitted = true)}>
		Check
	</button>
	{#if result}
		<p class="feedback" data-outcome={result.outcome} role="status">{result.feedback}</p>
	{/if}
</div>

<style>
	.match-root {
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
	.columns {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}
	.col {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	.chip {
		width: 100%;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 10px;
		background: var(--paper, #fafaf9);
		padding: 10px 12px;
		cursor: pointer;
		text-align: left;
	}
	.chip.selected,
	.chip.matched {
		border-color: var(--accent, #0f766e);
		background: color-mix(in srgb, var(--accent, #0f766e) 12%, white);
	}
	.hint {
		margin: 0;
		font-size: 12px;
		color: var(--ink-3, #78716c);
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
