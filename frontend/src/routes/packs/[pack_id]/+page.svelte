<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { page } from '$app/state';
	import { getPackStatus } from '$lib/api/learning-pack';
	import type { PackStatusResponse } from '$lib/types/learning-pack';

	let status = $state<PackStatusResponse | null>(null);
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setInterval> | null = null;
	const packId = $derived(page.params.pack_id ?? '');

	async function refresh() {
		try {
			status = await getPackStatus(packId);
			if (status.status === 'complete' || status.status === 'failed') {
				if (timer) clearInterval(timer);
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load pack.';
		}
	}

	onMount(() => {
		void refresh();
		timer = setInterval(() => void refresh(), 3000);
	});

	onDestroy(() => {
		if (timer) clearInterval(timer);
	});
</script>

<section class="pack-view">
	{#if error}
		<p class="error">{error}</p>
	{:else if status}
		<div class="header">
			<div>
				<p class="eyebrow">{status.learning_job_type}</p>
				<h1>{status.topic}</h1>
				<p>{status.completed_count} of {status.resource_count} ready - {status.status}</p>
			</div>
		</div>

		<div class="resources">
			{#each status.resources as resource}
				<article>
					<strong>{resource.label}</strong>
					<p>{resource.resource_type.replaceAll('_', ' ')} - {resource.phase}</p>
					{#if resource.generation_id}
						<a href={`/studio/generations/${resource.generation_id}`}>Open</a>
					{/if}
				</article>
			{/each}
		</div>

		<a class="quiz-link" href={`/packs/${encodeURIComponent(packId)}/items`}>
			Review shared quiz
		</a>
	{:else}
		<p>Loading pack...</p>
	{/if}
</section>

<style>
	.pack-view {
		display: grid;
		gap: 1rem;
	}

	.header,
	.resources article {
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 18px;
		background: rgba(255, 251, 244, 0.84);
		padding: 1rem;
	}

	.header {
		display: flex;
		gap: 0.75rem;
		justify-content: space-between;
		align-items: flex-start;
	}


	.eyebrow,
	h1,
	p {
		margin: 0;
	}

	.eyebrow {
		font-size: 0.78rem;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: #6b7c88;
	}

	.resources {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
		gap: 0.75rem;
	}

	.resources article {
		display: grid;
		gap: 0.45rem;
	}

	a {
		color: #24436a;
		font-weight: 700;
		text-decoration: none;
	}

	.quiz-link {
		justify-self: start;
		border: 1px solid rgba(36, 67, 106, 0.25);
		border-radius: 10px;
		background: white;
		padding: 0.65rem 0.9rem;
	}

	.error {
		color: #8d3a26;
	}
</style>
