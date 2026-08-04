<script lang="ts">
	import type { PackLearningPlan } from '$lib/types/learning-pack';

	let { plan }: { plan: PackLearningPlan } = $props();
</script>

<section class="plan-card">
	<p class="eyebrow">Shared plan</p>
	<h3>{plan.objective}</h3>
	{#if plan.success_criteria.length}
		<ul>
			{#each plan.success_criteria as criterion}
				<li>{criterion}</li>
			{/each}
		</ul>
	{/if}
	{#if plan.likely_misconceptions.length}
		<div class="misconceptions">
			<strong>Watch for</strong>
			<p>{plan.likely_misconceptions.join('; ')}</p>
		</div>
	{/if}
	{#if plan.shared_vocabulary.length}
		<div class="tags">
			{#each plan.shared_vocabulary as term}
				<span>{term}</span>
			{/each}
		</div>
	{/if}
	{#if plan.shared_examples.length}
		<p class="example">Anchor: {plan.shared_examples.join('; ')}</p>
	{/if}
</section>

<style>
	.plan-card {
		display: grid;
		gap: 0.75rem;
		padding: 1rem;
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.68);
	}

	.eyebrow,
	h3,
	p,
	ul {
		margin: 0;
	}

	.eyebrow {
		font-size: 0.76rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	h3 {
		font-size: 1.1rem;
	}

	ul {
		padding-left: 1.2rem;
	}

	.misconceptions {
		border-left: 3px solid #b96b4f;
		padding-left: 0.75rem;
		color: #6f3729;
	}

	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.tags span {
		border-radius: 999px;
		background: rgba(29, 158, 117, 0.1);
		padding: 0.22rem 0.6rem;
		color: #0b6a52;
		font-size: 0.82rem;
	}

	.example {
		color: #5f574d;
	}
</style>

