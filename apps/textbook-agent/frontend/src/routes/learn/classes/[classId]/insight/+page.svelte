<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';

	let ready = $state(false);
	let error = $state<string | null>(null);
	let insight = $state<any>(null);

	const classId = $derived(page.params.classId);

	onMount(async () => {
		if (!browser || !classId) return;
		try {
			const response = await apiFetch(`/api/v1/learn/analytics/classes/${classId}/overview`);
			await ensureOk(response);
			insight = await response.json();
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load insight';
			ready = true;
		}
	});
</script>

<main class="insight-page">
	<p class="eyebrow">Teacher insight</p>
	<h1>Class analytics</h1>
	<p class="lede"><a href={`/learn/classes/${classId}`}>← Class</a></p>
	{#if !ready}
		<p class="lede">Loading…</p>
	{:else if error}
		<p class="lede error">{error}</p>
	{:else if insight}
		<section class="cards">
			<article>
				<p class="eyebrow">Completion</p>
				<p>{insight.completion?.completed ?? 0} done / {insight.completion?.active ?? 0} active</p>
			</article>
			<article>
				<p class="eyebrow">Graded</p>
				<p>{insight.graded.score_earned}/{insight.graded.score_possible}</p>
				<small>{insight.graded.attempts} attempts</small>
			</article>
			<article>
				<p class="eyebrow">Practice</p>
				<p>{insight.practice.score_earned}/{insight.practice.score_possible}</p>
				<small>{insight.practice.attempts} attempts</small>
			</article>
		</section>

		<section>
			<p class="eyebrow">Concepts</p>
			<ul>
				{#each insight.concepts as row}
					<li>
						{row.concept_id} · {row.classification}
						{#if row.first_attempt_success === true}
							· first-try
						{:else if row.first_attempt_success === false}
							· eventual
						{/if}
					</li>
				{:else}
					<li>No concept evidence yet.</li>
				{/each}
			</ul>
		</section>

		<section>
			<p class="eyebrow">Misconceptions</p>
			<ul>
				{#each insight.misconceptions ?? [] as row}
					<li>{row.misconception_id} · {row.count}</li>
				{:else}
					<li>None flagged.</li>
				{/each}
			</ul>
		</section>

		<section>
			<p class="eyebrow">Item quality</p>
			<ul>
				{#each insight.item_quality ?? [] as row}
					<li>
						{row.interaction_id}: first {Math.round(row.first_attempt_success_rate * 100)}% ·
						retries {row.avg_retries.toFixed(1)}
						{#if row.review_recommended}
							· <strong>review recommended</strong>
						{/if}
					</li>
				{:else}
					<li>No items yet.</li>
				{/each}
			</ul>
		</section>
	{/if}
</main>

<style>
	.insight-page {
		max-width: 900px;
		margin: 0 auto;
		padding: 28px 18px 48px;
		color: var(--ink);
		background: var(--paper);
		min-height: 100vh;
	}
	.eyebrow {
		margin: 0 0 6px;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0 0 8px;
		font: 500 34px/1.1 Fraunces, Georgia, serif;
	}
	.lede {
		color: var(--ink-2);
	}
	.lede.error {
		color: var(--amber, #b45309);
	}
	.cards {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 12px;
		margin: 18px 0 22px;
	}
	.cards article {
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 14px;
	}
	ul {
		padding-left: 18px;
		color: var(--ink-2);
	}
	a {
		color: var(--accent);
		font-weight: 600;
		text-decoration: none;
	}
	@media (max-width: 720px) {
		.cards {
			grid-template-columns: 1fr;
		}
	}
</style>
