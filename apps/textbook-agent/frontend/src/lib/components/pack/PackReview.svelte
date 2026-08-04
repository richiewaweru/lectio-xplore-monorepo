<script lang="ts">
	import PackLearningPlanCard from './PackLearningPlanCard.svelte';
	import type { LearningPackPlan } from '$lib/types/learning-pack';

	let {
		plan,
		onBack,
		onConfirmed,
		generating = false,
		error = null
	}: {
		plan: LearningPackPlan;
		onBack: () => void;
		onConfirmed: (plan: LearningPackPlan) => void;
		generating?: boolean;
		error?: string | null;
	} = $props();

	function clonePlan(value: LearningPackPlan): LearningPackPlan {
		return JSON.parse(JSON.stringify(value)) as LearningPackPlan;
	}

	let initializedPackId = '';
	let localPlan = $state<LearningPackPlan | null>(null);
	const enabledCount = $derived(
		localPlan?.resources.filter((resource) => resource.enabled).length ?? 0
	);

	$effect(() => {
		if (initializedPackId !== plan.pack_id) {
			initializedPackId = plan.pack_id;
			localPlan = clonePlan(plan);
		}
	});

	function confirmLocalPlan() {
		if (localPlan) {
			onConfirmed(clonePlan(localPlan));
		}
	}
</script>

{#if localPlan}
<section class="review">
	<div class="header">
		<div>
			<p class="eyebrow">{localPlan.learning_job.job}</p>
			<h1>{localPlan.learning_job.topic}</h1>
			<p>{localPlan.learning_job.objective}</p>
		</div>
		<button type="button" onclick={onBack}>Back</button>
	</div>

	{#if localPlan.learning_job.class_signals.length}
		<div class="signals">
			{#each localPlan.learning_job.class_signals as signal}
				<span>{signal}</span>
			{/each}
		</div>
	{/if}

	<PackLearningPlanCard plan={localPlan.pack_learning_plan} />

	<section class="resources">
		<h2>Resources</h2>
		{#each localPlan.resources as resource}
			<label class="resource">
				<input type="checkbox" bind:checked={resource.enabled} />
				<div>
					<strong>{resource.order}. {resource.label}</strong>
					<p>{resource.purpose}</p>
					<span>{resource.resource_type.replaceAll('_', ' ')} / {resource.depth}</span>
				</div>
			</label>
		{/each}
	</section>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	<button
		class="primary"
		onclick={confirmLocalPlan}
		disabled={enabledCount === 0 || generating}
	>
		{generating ? 'Starting...' : `Generate ${enabledCount} resources`}
	</button>
</section>
{/if}

<style>
	.review {
		display: grid;
		gap: 1rem;
	}

	.header {
		display: flex;
		justify-content: space-between;
		gap: 1rem;
	}

	.eyebrow,
	h1,
	h2,
	p {
		margin: 0;
	}

	.eyebrow {
		font-size: 0.78rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	.signals {
		display: flex;
		flex-wrap: wrap;
		gap: 0.45rem;
	}

	.signals span,
	.resource span {
		border-radius: 999px;
		background: rgba(54, 101, 130, 0.1);
		padding: 0.22rem 0.6rem;
		color: #28516b;
		font-size: 0.82rem;
	}

	.resources {
		display: grid;
		gap: 0.75rem;
	}

	.resource {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.85rem;
		padding: 1rem;
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.68);
	}

	.resource div {
		display: grid;
		gap: 0.45rem;
	}

	button,
	.primary {
		border-radius: 999px;
		border: 1px solid rgba(36, 52, 63, 0.18);
		background: rgba(36, 52, 63, 0.05);
		color: #24343f;
		padding: 0.5rem 0.85rem;
		cursor: pointer;
	}

	.primary {
		width: fit-content;
		background: #24343f;
		color: #fff;
	}

	.primary:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.error {
		color: #8d3a26;
	}

	@media (max-width: 720px) {
		.header {
			display: grid;
		}
	}
</style>
