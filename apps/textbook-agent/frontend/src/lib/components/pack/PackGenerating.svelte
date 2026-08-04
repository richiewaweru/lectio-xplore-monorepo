<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { getPackStatus } from '$lib/api/learning-pack';
	import type { PackStatusResponse } from '$lib/types/learning-pack';

	let {
		packId,
		onComplete
	}: { packId: string; onComplete: (response: PackStatusResponse) => void } = $props();

	let status = $state<PackStatusResponse | null>(null);
	let error = $state<string | null>(null);
	let timer: ReturnType<typeof setInterval> | null = null;

	async function refresh() {
		try {
			status = await getPackStatus(packId);
			if (status.status === 'complete' || status.status === 'failed') {
				if (timer) clearInterval(timer);
				onComplete(status);
			}
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load pack status.';
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

<section class="generating">
	<div>
		<p class="eyebrow">Generating pack</p>
		<h1>{status?.topic ?? 'Preparing resources'}</h1>
		<p>{status ? `${status.completed_count} of ${status.resource_count} complete` : 'Starting...'}</p>
	</div>

	{#if error}
		<p class="error">{error}</p>
	{/if}

	<div class="rows">
		{#each status?.resources ?? [] as resource}
			<div class="row">
				<span class="dot phase-{resource.phase}"></span>
				<div>
					<strong>{resource.label}</strong>
					<p>{resource.phase}</p>
				</div>
				{#if resource.generation_id && resource.phase === 'done'}
					<a href={`/studio/generations/${resource.generation_id}`}>Open</a>
				{/if}
			</div>
		{/each}
	</div>
</section>

<style>
	.generating {
		display: grid;
		gap: 1rem;
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

	.rows {
		display: grid;
		gap: 0.7rem;
	}

	.row {
		display: grid;
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 0.75rem;
		padding: 0.9rem 1rem;
		border: 1px solid rgba(36, 52, 63, 0.12);
		border-radius: 16px;
		background: rgba(255, 255, 255, 0.68);
	}

	.dot {
		width: 0.72rem;
		height: 0.72rem;
		border-radius: 50%;
		background: #8a8379;
	}

	.phase-planning,
	.phase-queued {
		background: #b7832e;
	}

	.phase-generating {
		background: #286a8f;
	}

	.phase-done {
		background: #2f7c43;
	}

	.phase-failed {
		background: #9b3d2b;
	}

	a {
		color: #24436a;
		font-weight: 700;
		text-decoration: none;
	}

	.error {
		color: #8d3a26;
	}
</style>

