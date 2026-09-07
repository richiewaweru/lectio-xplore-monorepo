<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';

	type Tab = 'overview' | 'students' | 'assignments' | 'progress';

	let tab = $state<Tab>('overview');
	let ready = $state(false);
	let error = $state<string | null>(null);
	let detail = $state<{
		id: string;
		name: string;
		invite_code: string;
		learners: Array<{ learner_id: string; display_name: string; role: string; status: string }>;
		assignments: Array<{ id: string; title: string; mode: string; active: boolean }>;
		staff_roles: Array<{ teacher_user_id: string; role: string }>;
	} | null>(null);
	let insight = $state<any>(null);
	let newLearner = $state('');
	let assignTitle = $state('');
	let assignReleaseId = $state('');
	let assignMode = $state('rolling');

	const classId = $derived(page.params.classId);

	async function load() {
		if (!classId) return;
		const response = await apiFetch(`/api/v1/learn/classes/${classId}`);
		await ensureOk(response);
		detail = await response.json();
		const insightResp = await apiFetch(`/api/v1/learn/analytics/classes/${classId}/overview`);
		if (insightResp.ok) insight = await insightResp.json();
	}

	onMount(async () => {
		if (!browser) return;
		try {
			await load();
			ready = true;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Failed to load class';
			ready = true;
		}
	});

	async function addLearner() {
		if (!classId || !newLearner.trim()) return;
		const response = await apiFetch(`/api/v1/learn/classes/${classId}/learners`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ display_name: newLearner.trim() })
		});
		await ensureOk(response);
		newLearner = '';
		await load();
	}

	async function createAssignment() {
		if (!classId || !assignReleaseId.trim()) return;
		const response = await apiFetch('/api/v1/learn/assignments', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				learn_release_id: assignReleaseId.trim(),
				title: assignTitle.trim() || 'Assignment',
				class_ids: [classId],
				mode: assignMode
			})
		});
		await ensureOk(response);
		assignTitle = '';
		assignReleaseId = '';
		await load();
		tab = 'assignments';
	}
</script>

<main class="class-page">
	{#if !ready}
		<p class="lede">Loading…</p>
	{:else if error}
		<p class="lede error">{error}</p>
	{:else if detail}
		<p class="eyebrow">Teacher class</p>
		<h1>{detail.name}</h1>
		<p class="lede">Invite code <code>{detail.invite_code}</code> · owner/teacher/assistant ready</p>

		<nav class="tabs" aria-label="Class sections">
			{#each ['overview', 'students', 'assignments', 'progress'] as key}
				<button
					type="button"
					class:active={tab === key}
					onclick={() => (tab = key as Tab)}
				>
					{key}
				</button>
			{/each}
			<a href={`/learn/classes/${classId}/insight`}>Insight</a>
		</nav>

		{#if tab === 'overview'}
			<section class="panel">
				<p>Students: {detail.learners.length}</p>
				<p>Assignments: {detail.assignments.length}</p>
				<p>Staff roles: {detail.staff_roles.map((r) => r.role).join(', ') || 'owner'}</p>
			</section>
		{:else if tab === 'students'}
			<section class="panel">
				<form
					onsubmit={(e) => {
						e.preventDefault();
						void addLearner();
					}}
				>
					<label>
						Add learner (no email)
						<input bind:value={newLearner} placeholder="Display name" required />
					</label>
					<button type="submit" class="primary">Add</button>
				</form>
				<ul>
					{#each detail.learners as learner}
						<li>{learner.display_name} · {learner.status}</li>
					{:else}
						<li class="empty">No learners yet.</li>
					{/each}
				</ul>
			</section>
		{:else if tab === 'assignments'}
			<section class="panel">
				<form
					onsubmit={(e) => {
						e.preventDefault();
						void createAssignment();
					}}
				>
					<label>
						Published release id
						<input bind:value={assignReleaseId} required placeholder="LearnRelease UUID" />
					</label>
					<label>
						Title
						<input bind:value={assignTitle} placeholder="Homework 1" />
					</label>
					<label>
						Mode
						<select bind:value={assignMode}>
							<option value="rolling">rolling</option>
							<option value="snapshot">snapshot</option>
							<option value="selected">selected</option>
						</select>
					</label>
					<button type="submit" class="primary">Assign published lesson</button>
				</form>
				<ul>
					{#each detail.assignments as row}
						<li>{row.title} · {row.mode} · {row.active ? 'active' : 'closed'}</li>
					{:else}
						<li class="empty">No assignments yet.</li>
					{/each}
				</ul>
			</section>
		{:else}
			<section class="panel">
				{#if insight}
					<p>Completed instances: {insight.completion?.completed ?? 0}</p>
					<p>Active instances: {insight.completion?.active ?? 0}</p>
					<p>
						Graded {insight.graded?.score_earned ?? 0}/{insight.graded?.score_possible ?? 0}
					</p>
				{:else}
					<p class="empty">Progress aggregates unavailable.</p>
				{/if}
			</section>
		{/if}
	{/if}
</main>

<style>
	.class-page {
		max-width: 880px;
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
		font-size: 14px;
	}
	.lede.error {
		color: var(--amber, #b45309);
	}
	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin: 18px 0;
	}
	.tabs button,
	.tabs a {
		border: 1px solid var(--rule);
		border-radius: 999px;
		background: var(--surface);
		padding: 8px 12px;
		text-decoration: none;
		color: inherit;
		text-transform: capitalize;
		cursor: pointer;
	}
	.tabs button.active {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 12%, white);
	}
	.panel {
		border: 1px solid var(--rule);
		border-radius: 12px;
		background: var(--surface);
		padding: 16px;
		display: grid;
		gap: 12px;
	}
	form {
		display: grid;
		gap: 10px;
	}
	label {
		display: grid;
		gap: 6px;
		font-size: 12px;
		font-weight: 600;
	}
	input,
	select {
		border: 1px solid var(--rule);
		border-radius: 8px;
		padding: 10px 12px;
		background: var(--paper);
		color: inherit;
	}
	.primary {
		justify-self: start;
		border: 1px solid var(--accent);
		border-radius: 8px;
		background: var(--accent);
		color: white;
		padding: 9px 12px;
		font-weight: 600;
		cursor: pointer;
	}
	ul {
		margin: 0;
		padding-left: 18px;
		color: var(--ink-2);
	}
	.empty {
		color: var(--ink-3);
	}
	code {
		font: 500 12px 'IBM Plex Mono', monospace;
	}
</style>
