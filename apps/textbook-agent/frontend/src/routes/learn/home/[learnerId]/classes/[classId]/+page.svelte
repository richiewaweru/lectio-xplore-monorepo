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
	}

	let ready = $state(false);
	let error = $state<string | null>(null);
	let className = $state('Class');
	let todo = $state<HomeInstance[]>([]);
	let inProgress = $state<HomeInstance[]>([]);
	let completed = $state<HomeInstance[]>([]);

	const learnerId = $derived(page.params.learnerId);
	const classId = $derived(page.params.classId);

	onMount(async () => {
		if (!browser || !learnerId || !classId) return;
		try {
			const headers: Record<string, string> = {};
			const token = localStorage.getItem('x-learner-session');
			if (token) headers['X-Learner-Session'] = token;
			const homeResp = await apiFetch(`/api/v1/learn/learners/${learnerId}/home`, { headers });
			await ensureOk(homeResp);
			const home = await homeResp.json();
			const cls = (home.classes ?? []).find((c: { id: string }) => c.id === classId);
			className = cls?.name ?? 'Class';
			const instances: HomeInstance[] = home.instances ?? [];
			// Class-scoped: prefer assignment-linked instances; full list if teacher JWT view.
			todo = instances.filter((i) => i.status === 'active' && !i.score_possible);
			inProgress = instances.filter((i) => i.status === 'active');
			completed = instances.filter((i) => i.status === 'completed');
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load class';
			ready = true;
		}
	});
</script>

<main class="student-class">
	<p class="eyebrow">Student class</p>
	{#if !ready}
		<p>Loading…</p>
	{:else if error}
		<p class="error">{error}</p>
	{:else}
		<h1>{className}</h1>
		<p class="lede">To do · in progress · completed</p>
		{#each [
			{ title: 'To do', items: todo },
			{ title: 'In progress', items: inProgress },
			{ title: 'Completed', items: completed }
		] as section}
			<section>
				<p class="eyebrow">{section.title}</p>
				<ul>
					{#each section.items as item}
						<li>
							<a href={`/learn/instances/${item.id}`}>{item.learn_release_id.slice(0, 8)} · {item.status}</a>
						</li>
					{:else}
						<li class="empty">None</li>
					{/each}
				</ul>
			</section>
		{/each}
		<p><a href={`/learn/home/${learnerId}`}>← Home</a></p>
	{/if}
</main>

<style>
	.student-class {
		max-width: 720px;
		margin: 0 auto;
		padding: 28px 18px 48px;
		background: var(--paper);
		color: var(--ink);
		min-height: 100vh;
		display: grid;
		gap: 16px;
	}
	.eyebrow {
		margin: 0;
		color: var(--ink-3);
		font: 500 11px 'IBM Plex Mono', monospace;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	h1 {
		margin: 0;
		font: 500 32px/1.1 Fraunces, Georgia, serif;
	}
	.lede {
		margin: 0;
		color: var(--ink-2);
	}
	ul {
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
		display: grid;
		gap: 8px;
	}
	a {
		color: var(--accent);
		text-decoration: none;
		font-weight: 600;
	}
	.empty,
	.error {
		color: var(--ink-3);
	}
	.error {
		color: var(--amber, #b45309);
	}
</style>
