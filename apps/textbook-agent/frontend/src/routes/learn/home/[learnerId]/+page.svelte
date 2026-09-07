<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';

	interface HomeInstance {
		id: string;
		learn_release_id: string;
		assignment_id: string | null;
		status: string;
		score_earned: number;
		score_possible: number;
		current_section_id?: string | null;
	}

	let ready = $state(false);
	let error = $state<string | null>(null);
	let displayName = $state('');
	let buckets = $state<{
		due_soon: HomeInstance[];
		in_progress: HomeInstance[];
		completed: HomeInstance[];
		classes: Array<{ id: string; name: string }>;
	}>({ due_soon: [], in_progress: [], completed: [], classes: [] });

	const learnerId = $derived(page.params.learnerId);

	onMount(async () => {
		if (!browser || !learnerId) return;
		try {
			const headers: Record<string, string> = {};
			const token = localStorage.getItem('x-learner-session');
			if (token) headers['X-Learner-Session'] = token;
			const response = await apiFetch(`/api/v1/learn/learners/${learnerId}/home`, { headers });
			await ensureOk(response);
			const body = await response.json();
			displayName = body.display_name;
			buckets = body.buckets ?? {
				due_soon: body.instances?.filter((i: HomeInstance) => i.status === 'active' && i.assignment_id) ?? [],
				in_progress: body.instances?.filter((i: HomeInstance) => i.status === 'active') ?? [],
				completed: body.instances?.filter((i: HomeInstance) => i.status === 'completed') ?? [],
				classes: body.classes ?? []
			};
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load student home';
			ready = true;
		}
	});
</script>

<main class="student-home">
	<p class="eyebrow">Student home</p>
	{#if !ready}
		<p class="lede">Loading…</p>
	{:else if error}
		<p class="lede error">{error}</p>
	{:else}
		<h1>{displayName}</h1>
		<p class="lede">Due soon · in progress · completed · classes</p>

		{#each [
			{ key: 'due_soon', title: 'Due soon', items: buckets.due_soon },
			{ key: 'in_progress', title: 'In progress', items: buckets.in_progress },
			{ key: 'completed', title: 'Completed', items: buckets.completed }
		] as section}
			<section>
				<p class="eyebrow">{section.title}</p>
				<ul class="cards">
					{#each section.items as item (item.id)}
						<li>
							<a href={section.key === 'completed' ? `/learn/instances/${item.id}/outcome` : `/learn/instances/${item.id}`}>
								<span class="status">{item.status}</span>
								<strong>Release {item.learn_release_id.slice(0, 8)}</strong>
								<span class="score">{item.score_earned}/{item.score_possible}</span>
							</a>
						</li>
					{:else}
						<li class="empty">None.</li>
					{/each}
				</ul>
			</section>
		{/each}

		<section>
			<p class="eyebrow">Classes</p>
			<ul class="cards">
				{#each buckets.classes as cls}
					<li>
						<a href={`/learn/home/${learnerId}/classes/${cls.id}`}>
							<strong>{cls.name}</strong>
						</a>
					</li>
				{:else}
					<li class="empty">No classes yet.</li>
				{/each}
			</ul>
		</section>
	{/if}
</main>

<style>
	.student-home {
		max-width: 720px;
		margin: 0 auto;
		padding: 28px 18px 48px;
		color: var(--ink);
		background: var(--paper);
		min-height: 100vh;
		display: grid;
		gap: 18px;
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
		font-size: 14px;
		margin: 0;
	}
	.lede.error {
		color: var(--amber, #b45309);
	}
	.cards {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
		display: grid;
		gap: 10px;
	}
	.cards a {
		display: grid;
		gap: 4px;
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 14px;
		text-decoration: none;
		color: inherit;
	}
	.status {
		color: var(--accent);
		font: 500 11px 'IBM Plex Mono', monospace;
		text-transform: uppercase;
	}
	.score {
		color: var(--ink-3);
		font-size: 12px;
	}
	.empty {
		color: var(--ink-3);
		font-size: 14px;
	}
	@media (max-width: 720px) {
		h1 {
			font-size: 28px;
		}
	}
</style>
