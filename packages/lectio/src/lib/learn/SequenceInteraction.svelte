<script lang="ts">
	import { evaluateSequence, type FeedbackSpec } from '$lib/learn/interaction-contract';

	interface Step {
		id: string;
		label: string;
	}

	interface Props {
		prompt: string;
		steps: Step[];
		correctOrder: string[];
		feedback: FeedbackSpec;
		ariaLabel?: string;
	}

	let { prompt, steps, correctOrder, feedback, ariaLabel = prompt }: Props = $props();

	let order = $state<string[]>([]);
	let submitted = $state(false);

	$effect(() => {
		if (order.length === 0 && steps.length > 0) {
			order = steps.map((s) => s.id);
		}
	});

	const result = $derived(
		submitted ? evaluateSequence({ order: correctOrder }, { order }, feedback) : null
	);

	function move(index: number, dir: -1 | 1) {
		if (submitted) return;
		const next = index + dir;
		if (next < 0 || next >= order.length) return;
		const copy = [...order];
		[copy[index], copy[next]] = [copy[next], copy[index]];
		order = copy;
	}

	function labelFor(id: string) {
		return steps.find((s) => s.id === id)?.label ?? id;
	}
</script>

<div class="seq-root" aria-label={ariaLabel} data-testid="sequence-interaction">
	<p class="prompt">{prompt}</p>
	<ol class="steps">
		{#each order as id, index (id)}
			<li>
				<span class="label">{labelFor(id)}</span>
				<div class="moves">
					<button
						type="button"
						aria-label={`Move ${labelFor(id)} up`}
						disabled={submitted || index === 0}
						onclick={() => move(index, -1)}
					>
						↑
					</button>
					<button
						type="button"
						aria-label={`Move ${labelFor(id)} down`}
						disabled={submitted || index === order.length - 1}
						onclick={() => move(index, 1)}
					>
						↓
					</button>
				</div>
			</li>
		{/each}
	</ol>
	<button type="button" class="submit" disabled={submitted} onclick={() => (submitted = true)}>Check</button>
	{#if result}
		<p class="feedback" data-outcome={result.outcome} role="status">{result.feedback}</p>
	{/if}
</div>

<style>
	.seq-root {
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
	.steps {
		margin: 0;
		padding: 0;
		list-style: none;
		display: grid;
		gap: 8px;
	}
	.steps li {
		display: flex;
		justify-content: space-between;
		gap: 10px;
		align-items: center;
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 10px;
		background: var(--paper, #fafaf9);
		padding: 8px 10px;
	}
	.moves {
		display: flex;
		gap: 4px;
	}
	.moves button {
		border: 1px solid var(--rule, #d6d3d1);
		border-radius: 6px;
		background: white;
		width: 28px;
		height: 28px;
		cursor: pointer;
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
