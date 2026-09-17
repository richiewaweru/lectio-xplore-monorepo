<script lang="ts">
	interface Step {
		id: string;
		label: string;
	}

	interface Props {
		steps: Step[];
		currentId: string;
		completedIds?: string[];
	}

	let { steps, currentId, completedIds = [] }: Props = $props();

	function state(id: string): 'done' | 'current' | 'todo' {
		if (completedIds.includes(id)) return 'done';
		if (id === currentId) return 'current';
		return 'todo';
	}
</script>

<ol class="steps">
	{#each steps as step, i}
		{@const s = state(step.id)}
		<li class="step step-{s}" aria-current={s === 'current' ? 'step' : undefined}>
			<span class="mark" aria-hidden="true">
				{#if s === 'done'}✓{:else}{i + 1}{/if}
			</span>
			<span class="label">{step.label}</span>
		</li>
	{/each}
</ol>

<style>
	.steps {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-3);
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.step {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		color: var(--ink-3);
		font-size: 0.8125rem;
		font-weight: 500;
	}
	.mark {
		display: grid;
		place-items: center;
		width: 1.4rem;
		height: 1.4rem;
		border-radius: 50%;
		border: 1px solid var(--rule);
		font-size: 0.7rem;
		background: var(--surface);
	}
	.step-done {
		color: var(--success);
	}
	.step-done .mark {
		background: var(--success-soft);
		border-color: transparent;
	}
	.step-current {
		color: var(--ink);
	}
	.step-current .mark {
		background: var(--accent);
		border-color: var(--accent);
		color: #fff;
	}
</style>
