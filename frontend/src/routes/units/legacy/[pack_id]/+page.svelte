<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { getLegacyUnitWrapper } from '$lib/api/units';
	import type { LegacyUnitWrapper } from '$lib/types/units';

	let wrapper = $state<LegacyUnitWrapper | null>(null);
	let error = $state<string | null>(null);

	onMount(async () => {
		try {
			wrapper = await getLegacyUnitWrapper(page.params.pack_id ?? '');
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not load this legacy unit.';
		}
	});
</script>

<svelte:head><title>{wrapper ? `${wrapper.title} · Legacy unit` : 'Legacy unit'}</title></svelte:head>

<main class="legacy-unit">
	<a class="back" href="/units">← Units</a>
	{#if error}
		<p class="error" role="alert">{error}</p>
	{:else if wrapper}
		<header>
			<p class="eyebrow">Compatibility · one lesson</p>
			<h1>{wrapper.title}</h1>
			<p>{wrapper.subject} · {wrapper.completed_count}/{wrapper.resource_count} resources complete</p>
		</header>
		<section>
			<p class="eyebrow">Destination</p>
			<h2>{wrapper.destination_objective}</h2>
			<p>This is a read-only view of the existing pack. No data was migrated or rewritten.</p>
		</section>
		<section>
			<p class="eyebrow">Lesson resources</p>
			{#if wrapper.lesson.generation_ids.length > 0}
				<div class="resources">
					{#each wrapper.lesson.generation_ids as generationId, index}
						<a href={`/studio/generations/${encodeURIComponent(generationId)}`}>
							<span>Resource {index + 1}</span><strong>Open in Legacy Studio →</strong>
						</a>
					{/each}
				</div>
			{:else}
				<p>No generated resources are attached to this pack yet.</p>
			{/if}
		</section>
	{:else}
		<p role="status">Loading legacy unit…</p>
	{/if}
</main>

<style>
	.legacy-unit { max-width: 900px; margin: 0 auto; padding: 48px 28px 80px; }
	.back { color: var(--ink-2); font-size: 13px; text-decoration: none; }
	header, section { margin-top: 28px; border: 1px solid var(--rule); border-radius: 18px; background: var(--surface); padding: 28px; }
	.eyebrow { margin: 0 0 8px; color: var(--ink-3); font: 500 11px 'IBM Plex Mono', monospace; letter-spacing: .1em; text-transform: uppercase; }
	h1, h2 { margin: 0; font-family: Fraunces, Georgia, serif; font-weight: 500; }
	h1 { font-size: 38px; } h2 { font-size: 24px; }
	header p:last-child, section > p:last-child { color: var(--ink-2); }
	.resources { display: grid; margin-top: 18px; border-top: 1px solid var(--rule); }
	.resources a { display: flex; justify-content: space-between; gap: 20px; padding: 18px 4px; border-bottom: 1px solid var(--rule); color: inherit; text-decoration: none; }
	.resources strong { color: var(--accent); font-size: 13px; }
	.error { margin-top: 28px; color: #8b1e1e; }
</style>
