<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';
	import { PageHeader, Card, EmptyState, InlineError, Badge } from '$lib/ui';

	let classes = $state<Array<{ id: string; name: string; invite_code: string }>>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			const response = await apiFetch('/api/v1/learn/classes');
			await ensureOk(response);
			classes = await response.json();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load classes.';
		} finally {
			loading = false;
		}
	});
</script>

<PageHeader
	title="Insights"
	description="See how learners are progressing across your classes."
/>

{#if error}
	<InlineError message={error} />
{:else if loading}
	<p class="muted">Loading classes…</p>
{:else if classes.length === 0}
	<EmptyState
		title="No classes yet"
		description="Create a class, assign a published Learn lesson, then return here for progress."
	/>
{:else}
	<div class="grid">
		{#each classes as row}
			<Card href={`/classes/${row.id}?tab=insights`} padding="md">
				<div class="row">
					<h2>{row.name}</h2>
					<Badge tone="info">Insights</Badge>
				</div>
				<p>Open overview and concept evidence for this class.</p>
			</Card>
		{/each}
	</div>
{/if}

<style>
	.grid {
		display: grid;
		gap: var(--space-4);
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
	}
	.row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-2);
	}
	h2 {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 600;
	}
	p {
		margin: 0.45rem 0 0;
		color: var(--ink-2);
		font-size: 0.875rem;
	}
	.muted {
		color: var(--ink-2);
	}
</style>
