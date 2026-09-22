<script lang="ts">
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { apiFetch } from '$lib/api/client';
	import { ensureOk } from '$lib/api/errors';
	import { PageHeader, Tabs, Button, InlineError, EmptyState, Badge } from '$lib/ui';

	type Tab = 'overview' | 'students' | 'assignments' | 'progress' | 'insights';

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
	let busy = $state(false);

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
		const q = page.url.searchParams.get('tab');
		if (q === 'insights' || q === 'insight') tab = 'insights';
		else if (q === 'students' || q === 'assignments' || q === 'progress' || q === 'overview') {
			tab = q;
		}
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
		busy = true;
		try {
			const response = await apiFetch(`/api/v1/learn/classes/${classId}/learners`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ display_name: newLearner.trim() })
			});
			await ensureOk(response);
			newLearner = '';
			await load();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Could not add learner';
		} finally {
			busy = false;
		}
	}
</script>

{#if !ready}
	<p class="muted">Loading…</p>
{:else if error && !detail}
	<InlineError message={error} />
{:else if detail}
	<PageHeader title={detail.name} description={`Invite code ${detail.invite_code} · students join at /join`}>
		{#snippet breadcrumb()}
			<a href="/classes">Classes</a>
			<span>/</span>
			<span>{detail?.name ?? ''}</span>
		{/snippet}
		{#snippet actions()}
			<Badge tone="info">Invite {detail?.invite_code ?? ''}</Badge>
		{/snippet}
	</PageHeader>

	<Tabs
		active={tab}
		tabs={[
			{ id: 'overview', label: 'Overview' },
			{ id: 'students', label: 'Students' },
			{ id: 'assignments', label: 'Assignments' },
			{ id: 'progress', label: 'Progress' },
			{ id: 'insights', label: 'Insights' }
		]}
		onSelect={(id) => (tab = id as Tab)}
	/>

	{#if tab === 'overview'}
		<section class="panel">
			<p><strong>{detail.learners.length}</strong> students</p>
			<p><strong>{detail.assignments.filter((a) => a.active).length}</strong> active assignments</p>
			{#if insight}
				<p>
					Completion: {insight.completion?.completed ?? 0} completed ·
					{insight.completion?.active ?? 0} in progress
				</p>
			{/if}
		</section>
	{:else if tab === 'students'}
		<section class="panel">
			<form
				class="row-form"
				onsubmit={(e) => {
					e.preventDefault();
					void addLearner();
				}}
			>
				<input bind:value={newLearner} placeholder="Student display name" required />
				<Button type="submit" busy={busy}>Add student</Button>
			</form>
			<ul>
				{#each detail.learners as learner}
					<li>{learner.display_name} · {learner.status}</li>
				{:else}
					<li class="empty">No students yet. Share the invite code or add a name.</li>
				{/each}
			</ul>
		</section>
	{:else if tab === 'assignments'}
		<section class="panel">
			<p class="hint">
				Assign from a Learn lesson’s Publish flow. Titles appear here — no release IDs needed.
			</p>
			<ul>
				{#each detail.assignments as row}
					<li>
						<strong>{row.title}</strong>
						<span class="meta">{row.mode} · {row.active ? 'active' : 'closed'}</span>
					</li>
				{:else}
					<li class="empty">No lessons assigned yet. Publish a Learn lesson and assign it to this class.</li>
				{/each}
			</ul>
		</section>
	{:else if tab === 'progress'}
		<section class="panel">
			{#if insight}
				<p>Completed: {insight.completion?.completed ?? 0}</p>
				<p>In progress: {insight.completion?.active ?? 0}</p>
				<p>
					Graded score: {insight.graded?.score_earned ?? 0}/{insight.graded?.score_possible ?? 0}
				</p>
			{:else}
				<EmptyState title="No progress yet" description="Assign a lesson and have students start it." />
			{/if}
		</section>
	{:else}
		<section class="panel">
			<p>
				<a href={`/learn/classes/${classId}/insight`}>Open detailed teacher insight →</a>
			</p>
			{#if insight}
				<pre class="insight">{JSON.stringify(insight, null, 2)}</pre>
			{/if}
		</section>
	{/if}
{/if}

<style>
	.muted {
		color: var(--ink-2);
	}
	.panel {
		border: 1px solid var(--rule);
		border-radius: var(--radius-lg);
		background: var(--surface);
		padding: var(--space-5);
		display: grid;
		gap: var(--space-3);
	}
	.row-form {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	input {
		flex: 1;
		min-width: 180px;
		padding: 0.55rem 0.7rem;
		border: 1px solid var(--rule);
		border-radius: var(--radius-md);
		font: inherit;
	}
	ul {
		margin: 0;
		padding-left: 1.1rem;
		color: var(--ink-2);
	}
	.empty {
		color: var(--ink-3);
		list-style: none;
		margin-left: -1.1rem;
	}
	.meta {
		margin-left: 0.5rem;
		color: var(--ink-3);
		font-size: 0.85rem;
	}
	.hint {
		margin: 0;
		color: var(--ink-2);
		font-size: 0.875rem;
	}
	.insight {
		overflow: auto;
		font-size: 0.75rem;
		background: var(--paper);
		padding: 0.75rem;
		border-radius: var(--radius-md);
	}
	a {
		color: var(--accent);
	}
</style>
