<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';

	let ready = $state(false);
	let error = $state<string | null>(null);
	let status = $state('');
	let graded = $state({ attempts: 0, score_earned: 0, score_possible: 0 });
	let practice = $state({ attempts: 0, score_earned: 0, score_possible: 0 });
	let concepts = $state<Array<{ concept_id: string; classification: string }>>([]);
	let learnerId = $state('');

	const instanceId = $derived(page.params.instanceId);

	onMount(async () => {
		if (!browser || !instanceId) return;
		try {
			const headers: Record<string, string> = {};
			const token = localStorage.getItem('x-learner-session');
			if (token) headers['X-Learner-Session'] = token;
			const response = await apiFetch(`/api/v1/learn/instances/${instanceId}`, { headers });
			await ensureOk(response);
			const body = await response.json();
			status = body.status;
			graded = body.graded ?? graded;
			practice = body.practice ?? practice;
			learnerId = body.learner_id;
			const states = await apiFetch(
				`/api/v1/learn/learners/${body.learner_id}/rebuild-concept-states`,
				{ method: 'POST', headers }
			);
			if (states.ok) {
				const rows = await states.json();
				concepts = rows.map((r: any) => ({
					concept_id: r.concept_id,
					classification: r.classification
				}));
			}
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load outcome';
			ready = true;
		}
	});
</script>

<main class="outcome-page">
	<p class="eyebrow">Lesson outcome</p>
	{#if !ready}
		<p>Loading…</p>
	{:else if error}
		<p class="error">{error}</p>
	{:else}
		<h1>Your results</h1>
		<p class="lede">Status: {status}</p>
		<section class="cards">
			<article>
				<p class="eyebrow">Graded</p>
				<p>{graded.score_earned}/{graded.score_possible}</p>
				<small>{graded.attempts} attempts</small>
			</article>
			<article>
				<p class="eyebrow">Practice</p>
				<p>{practice.score_earned}/{practice.score_possible}</p>
				<small>{practice.attempts} attempts</small>
			</article>
		</section>
		<section>
			<p class="eyebrow">Concept bands</p>
			<ul>
				{#each concepts as row}
					<li>{row.concept_id} · {row.classification}</li>
				{:else}
					<li>No concept evidence yet.</li>
				{/each}
			</ul>
		</section>
		{#if learnerId}
			<p><a href={`/learn/home/${learnerId}`}>← Back home</a></p>
		{/if}
	{/if}
</main>

<style>
	.outcome-page {
		max-width: 720px;
		margin: 0 auto;
		padding: 28px 18px 48px;
		background: var(--paper);
		color: var(--ink);
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
		margin: 0;
		font: 500 34px/1.1 Fraunces, Georgia, serif;
	}
	.lede {
		color: var(--ink-2);
	}
	.cards {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
		margin: 18px 0;
	}
	.cards article {
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 14px;
	}
	ul {
		color: var(--ink-2);
	}
	a {
		color: var(--accent);
		font-weight: 600;
		text-decoration: none;
	}
	.error {
		color: var(--amber, #b45309);
	}
	@media (max-width: 720px) {
		.cards {
			grid-template-columns: 1fr;
		}
	}
</style>
