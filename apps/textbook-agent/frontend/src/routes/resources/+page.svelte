<script lang="ts">
	import { onMount } from 'svelte';
	import { listUnits } from '$lib/api/units';
	import type { Unit } from '$lib/types/units';
	import { PageHeader, Card, EmptyState, InlineError } from '$lib/ui';

	let units = $state<Unit[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			units = await listUnits();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load units.';
		} finally {
			loading = false;
		}
	});
</script>

<PageHeader
	title="Resources"
	description="Open a unit and use its Resources tab to compose full lessons, homework, quizzes, and more."
/>

{#if error}
	<InlineError message={error} />
{:else if loading}
	<p class="muted">Loading units…</p>
{:else if units.length === 0}
	<EmptyState
		title="No units yet"
		description="Create a unit first, then compose printable resources from its lessons."
	/>
{:else}
	<div class="grid">
		{#each units as unit}
			<Card href={`/units/${unit.id}?tab=resources`} padding="md">
				<h2>{unit.title}</h2>
				<p>{unit.subject} · {unit.grade_level}</p>
				<span class="cta">Open resources →</span>
			</Card>
		{/each}
	</div>
{/if}

<style>
	.grid {
		display: grid;
		gap: var(--space-4);
		grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
	}
	h2 {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 600;
	}
	p {
		margin: 0.35rem 0 0;
		color: var(--ink-2);
		font-size: 0.875rem;
	}
	.cta {
		display: inline-block;
		margin-top: var(--space-3);
		color: var(--accent);
		font-size: 0.8125rem;
		font-weight: 550;
	}
	.muted {
		color: var(--ink-2);
	}
</style>
